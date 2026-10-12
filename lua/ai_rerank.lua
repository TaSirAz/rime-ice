-- Optional asynchronous local-model prototype. The worker never blocks Rime.
local M = { processor = {}, filter = {} }
local states = {}
local serial = 0

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

M.processor.init = get_state
M.processor.fini = finish
function M.processor.func(key, env)
  if not env.ai_enabled then return 2 end
  local s = env.ai_state
  local repr = key:repr()
  if repr == "Control+Shift+BackSpace" then
    reset(s)
    return 1
  end
  if repr == "Control+Shift+r" or repr == "Control+Shift+R" then
    if env.engine.context:is_composing() then
      env.engine.context:refresh_non_confirmed_composition()
      return 1
    end
  end
  if repr == "Return" and not env.engine.context:is_composing() then reset(s) end
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

M.filter.init = get_state
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
      and env.engine.context.input:match("^[a-z']+$") and s.context ~= ""
  if enabled and list[1].quality and list[1].quality >= 99 then enabled = false end
  if enabled then
    local texts = {}
    for i, c in ipairs(list) do texts[i] = quote(c.text) end
    local signature = s.context .. "\n" .. env.engine.context.input .. "\n" .. table.concat(texts, ",")
    if signature ~= s.signature then
      s.signature = signature
      s.generation = s.generation + 1
      s.request_id = s.id .. "-" .. tostring(s.generation)
      s.request_time = os.time()
      local tmp = env.ai_dir .. "/request.tmp"
      local file = io.open(tmp, "wb")
      if file then
        file:write('{"id":' .. quote(s.request_id) .. ',"context":' .. quote(s.context)
          .. ',"candidates":[' .. table.concat(texts, ",") .. ']}')
        file:close()
        -- Windows rename cannot overwrite an existing file; remove only bridge request.
        os.remove(env.ai_dir .. "/request.json")
        os.rename(tmp, env.ai_dir .. "/request.json")
      end
    end
    local file = io.open(env.ai_dir .. "/response.txt", "rb")
    if file then
      local id, order = file:read("*l"), file:read("*l")
      file:close()
      if id == s.request_id and order then
        local reordered, seen = {}, {}
        for number in order:gmatch("%d+") do
          local i = tonumber(number)
          if list[i] and not seen[i] then
            reordered[#reordered + 1] = list[i]
            seen[i] = true
          end
        end
        if #reordered == #list then list = reordered end
      end
    end
  end
  for _, c in ipairs(list) do yield(c) end
  for c in iterator, iterator_state do yield(c) end
end
return M
