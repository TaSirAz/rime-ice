-- Optional asynchronous local-model prototype. The worker never blocks Rime.
local M = { processor = {}, filter = {} }
local states = {}
local serial = 0
local VERSION = "sentence-ranking-v6"

local function status(env, event, detail)
  if not env.ai_dir then return end
  pcall(function()
    local path = env.ai_dir .. "/status.log"
    local file = io.open(path, "ab")
    if file then
      file:write(VERSION .. "\t" .. event .. "\t" .. tostring(detail or "") .. "\n")
      file:close()
    end
  end)
end

local function get_state(env)
  local ctx = env.engine.context
  local id = ctx:get_property("_ai_rerank_session")
  if id == "" then
    serial = serial + 1
    id = tostring(os.time()) .. "-" .. tostring(serial)
    ctx:set_property("_ai_rerank_session", id)
  end
  if not states[id] then
    local state = { id = id, context = "", generation = 0, last = os.time(), refs = 0 }
    state.connection = ctx.commit_notifier:connect(function(c)
      if not state.enabled then return end
      local text = c:get_commit_text()
      if text and text ~= "" then
        state.context = state.context .. text
        -- Keep a UTF-8-safe tail, at most 128 characters.
        local n = utf8.len(state.context)
        if n and n > 128 then
          state.context = state.context:sub(utf8.offset(state.context, n - 127))
        end
        state.generation = state.generation + 1
        state.last = os.time()
      end
    end)
    states[id] = state
  end
  env.ai_state = states[id]
  env.ai_state.refs = env.ai_state.refs + 1
  env.ai_enabled = env.engine.schema.config:get_bool("ai_rerank/enabled") or false
  env.ai_state.enabled = env.ai_enabled
  env.ai_dir = env.engine.schema.config:get_string("ai_rerank/bridge_dir")
  local auto = env.engine.schema.config:get_bool("ai_rerank/auto_refresh")
  env.ai_auto = auto == nil or auto
end

local function finish(env)
  local s = env.ai_state
  if not s then return end
  s.refs = s.refs - 1
  if s.refs == 0 then
    s.connection:disconnect()
    states[s.id] = nil
  end
end

local function reset(s)
  s.context = ""
  s.generation = s.generation + 1
  s.signature = nil
  s.last = os.time()
end

-- Include confirmed/selected segments that are still in the composition.
-- Never include the active candidate itself in its own conditioning prefix.
local function scoring_context(ctx, start, history)
  local parts = { history }
  if start and start > 0 then
    local ok, segments = pcall(function()
      return ctx.composition:toSegmentation():get_segments()
    end)
    if ok and segments then
      for _, segment in ipairs(segments) do
        if segment._end <= start
            and (segment.status == "kSelected" or segment.status == "kConfirmed") then
          local candidate = segment:get_selected_candidate()
          if candidate then parts[#parts + 1] = candidate.text end
        end
      end
    end
  end
  local text = table.concat(parts)
  local n = utf8.len(text)
  if n and n > 128 then text = text:sub(utf8.offset(text, n - 127)) end
  return text
end

M.processor.init = function(env)
  get_state(env)
  status(env, "processor_loaded", "enabled=" .. tostring(env.ai_enabled))
end
M.processor.fini = finish
function M.processor.func(key, env)
  if not env.ai_enabled then return 2 end
  local s = env.ai_state
  -- VK_F24 notification from the local worker; never insert text.
  if env.ai_auto and key.keycode == 0xffd5 then
    if not key:release() and env.engine.context:is_composing()
        and s.request_input == env.engine.context.input
        and s.request_caret == env.engine.context.caret_pos
        and s.request_context == scoring_context(env.engine.context, s.request_start, s.context) then
      local file = env.ai_dir and io.open(env.ai_dir .. "/response.txt", "rb")
      if file then
        local id = file:read("*l")
        file:close()
        if id then id = id:gsub("\r$", "") end
        if id == s.request_id then
          status(env, "auto_refresh_received", id)
          local refreshed = env.engine.context:refresh_non_confirmed_composition()
          if not refreshed then env.engine.context:set_input(env.engine.context.input) end
        end
      end
    end
    return 1
  end
  -- Rime repr() uses modifier bit order (Shift+Control), not config text order.
  if key:release() then return 2 end
  local ctrl_shift = key:ctrl() and key:shift() and not key:alt() and not key:super()
  if ctrl_shift then status(env, "ctrl_shift_key", key:repr() .. " code=" .. tostring(key.keycode)) end
  if ctrl_shift and key.keycode == 0xff08 then
    reset(s)
    return 1
  end
  if ctrl_shift and (key.keycode == string.byte("r") or key.keycode == string.byte("R")) then
    if env.engine.context:is_composing() then
      status(env, "refresh_received", s.request_id or "no_request")
      local refreshed = env.engine.context:refresh_non_confirmed_composition()
      if not refreshed then
        env.engine.context:set_input(env.engine.context.input)
      end
      return 1
    end
  end
  if key.keycode == 0xff0d and not env.engine.context:is_composing() then reset(s) end
  if os.time() - s.last > 60 then reset(s) end
  return 2
end

local function quote(text)
  return '"' .. text:gsub('[%z\1-\31\\"]', function(c)
    if c == '"' then return '\\"' end
    if c == '\\' then return '\\\\' end
    return string.format('\\u%04x', string.byte(c))
  end) .. '"'
end

M.filter.init = function(env)
  get_state(env)
  status(env, "filter_loaded", "enabled=" .. tostring(env.ai_enabled))
end
M.filter.fini = finish
function M.filter.func(input, env)
  local list = {}
  -- Bound candidate consumption: preserve the lazy iterator for remaining words.
  local iterator, iterator_state = input:iter()
  for _ = 1, 8 do
    local c = iterator(iterator_state)
    if not c then break end
    list[#list + 1] = c
  end
  local s = env.ai_state
  local enabled = env.ai_enabled and env.ai_dir and #list >= 2
      and env.engine.context.input:match("^[a-z']+$")
  if enabled and list[1].quality and list[1].quality >= 99 then enabled = false end
  if enabled then
    local texts, spans = {}, {}
    for i, c in ipairs(list) do
      texts[i] = quote(c.text)
      spans[i] = quote(tostring(c.start) .. ":" .. tostring(c._end))
    end
    local context = scoring_context(env.engine.context, list[1].start, s.context)
    local focus = ""
    if env.ai_auto then
      local file = io.open(env.ai_dir .. "/focus.txt", "rb")
      if file then
        local token, stamp = file:read("*l"), tonumber(file:read("*l"))
        file:close()
        if token and stamp and math.abs(os.time() - stamp) <= 2 then
          focus = token:gsub("\r$", "")
        end
      end
    end
    local signature = context .. "\n" .. env.engine.context.input .. "\n"
      .. tostring(env.engine.context.caret_pos) .. "\n" .. table.concat(texts, ",")
      .. "\n" .. table.concat(spans, ",")
    if signature ~= s.signature then
      s.signature = signature
      s.generation = s.generation + 1
      s.request_id = s.id .. "-" .. tostring(s.generation)
      s.request_time = os.time()
      s.request_input = env.engine.context.input
      s.request_context = context
      s.request_start = list[1].start
      s.request_caret = env.engine.context.caret_pos
      local tmp = env.ai_dir .. "/request.tmp"
      local file = io.open(tmp, "wb")
      if file then
        file:write('{"id":' .. quote(s.request_id) .. ',"context":' .. quote(context)
          .. ',"focus":' .. quote(focus) .. ',"auto_refresh":' .. tostring(env.ai_auto == true)
          .. ',"spans":[' .. table.concat(spans, ",") .. ']'
          .. ',"candidates":[' .. table.concat(texts, ",") .. ']}')
        file:close()
        -- Windows rename cannot overwrite an existing file; remove only bridge request.
        os.remove(env.ai_dir .. "/request.json")
        local renamed = os.rename(tmp, env.ai_dir .. "/request.json")
        status(env, renamed and "request_written" or "request_write_failed", s.request_id)
      end
    end
    local file = io.open(env.ai_dir .. "/response.txt", "rb")
    if file then
      local id, order = file:read("*l"), file:read("*l")
      file:close()
      -- Binary mode preserves CR from Windows CRLF; strip it before ID matching.
      if id then id = id:gsub("\r$", "") end
      if order then order = order:gsub("\r$", "") end
      if id == s.request_id and order then
        local reordered, seen = {}, {}
        for number in order:gmatch("%d+") do
          local i = tonumber(number)
          if list[i] and not seen[i] then
            reordered[#reordered + 1] = list[i]
            seen[i] = true
          end
        end
        if #reordered == #list then
          list = reordered
          local first = list[1]
          list[1] = ShadowCandidate(first, first.type, first.text, (first.comment or "") .. " [AI]")
          status(env, "result_applied", id)
        else
          status(env, "invalid_order", id)
        end
      else
        status(env, "result_mismatch", "expected=" .. tostring(s.request_id) .. " got=" .. tostring(id))
      end
    end
  end
  for _, c in ipairs(list) do yield(c) end
  for c in iterator, iterator_state do yield(c) end
end
return M
