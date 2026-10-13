-- Run from repository root: lua tools/ai_rerank/test_filter.lua
-- Match librime-lua TranslationReg.raw_iter: returns next function AND state.
local module = dofile("lua/ai_rerank.lua")
local output = {}
function yield(candidate) output[#output + 1] = candidate end

local function translation(count)
  local state = { index = 0, candidates = {} }
  for i = 1, count do
    state.candidates[i] = { text = "candidate-" .. i, quality = 1 }
  end
  local function next_candidate(t)
    assert(t == state, "Missing Translation iterator state")
    t.index = t.index + 1
    return t.candidates[t.index]
  end
  return { iter = function() return next_candidate, state end }, state
end

for _, count in ipairs({0, 1, 2, 8, 9, 20}) do
  output = {}
  local input, state = translation(count)
  module.filter.func(input, { ai_enabled = false, ai_state = { context = "" } })
  assert(#output == count, "Candidate count changed: " .. count)
  for i = 1, count do
    assert(output[i] == state.candidates[i], "Original candidate identity/order changed")
  end
end
print("PASS: iterator state and all candidates preserved for 0/1/2/8/9/20 entries")

-- Exercise actual request generation without accessing a user's bridge directory.
local original_open, original_remove, original_rename = io.open, os.remove, os.rename
local request
io.open = function(path, mode)
  if mode == "rb" then return nil end
  return {
    write = function(_, text)
      if path:match("/request.tmp$") then request = text end
    end,
    close = function() end,
  }
end
os.remove = function() return true end
os.rename = function() return true end

local function run_request(history, start, segments)
  request = nil
  output = {}
  local input, state = translation(2)
  state.candidates[1].text = "我們達成公事"
  state.candidates[2].text = "我們達成共識"
  for _, candidate in ipairs(state.candidates) do
    candidate.start, candidate._end = start, 23
  end
  local ctx = {
    input = "womendachenggongshi", caret_pos = 18,
    composition = {
      toSegmentation = function()
        return { get_segments = function() return segments or {} end }
      end,
    },
  }
  local env = {
    ai_enabled = true, ai_auto = false, ai_dir = "mock",
    ai_state = { id = "test", context = history, generation = 0 },
    engine = { context = ctx },
  }
  module.filter.func(input, env)
  assert(#output == 2, "Request generation dropped candidates")
  assert(request, "No request before Enter")
  return request, env
end

local text, env = run_request("", 0)
assert(text:find('"context":""', 1, true), "Empty history must still submit request")
assert(text:find('"spans":["0:23","0:23"]', 1, true), "Candidate coverage missing")
assert(env.ai_state.request_caret == 18, "Caret was not captured")
local prefix_segment = {
  _end = 8, status = "kConfirmed",
  get_selected_candidate = function() return { text = "我們達成" } end,
}
local active_segment = {
  _end = 23, status = "kGuess",
  get_selected_candidate = function() error("Must not read active candidate") end,
}
text = run_request("今天", 8, { prefix_segment, active_segment })
assert(text:find('"context":"今天我們達成"', 1, true), "Uncommitted prefix missing")
io.open, os.remove, os.rename = original_open, original_remove, original_rename
print("PASS: pre-Enter requests, composing prefix, spans and caret")

-- Candidate visibility must follow this request's result, not a stale response.
local old_open, old_remove, old_rename, old_time = io.open, os.remove, os.rename, os.time
local old_shadow = ShadowCandidate
local now, files = 1000, {}
local focus_token = "control"
io.open = function(path, mode)
  local name = path:match("/([^/]+)$")
  if mode == "rb" then
    local content = files[name]
    if not content then return nil end
    local lines = {}
    for line in content:gmatch("([^\n]*)\n") do lines[#lines + 1] = line end
    local index = 0
    return {
      read = function() index = index + 1; return lines[index] end,
      close = function() end,
    }
  end
  return { write = function(_, content) files[name] = content end, close = function() end }
end
os.remove = function() return true end
os.rename = function() return true end
os.time = function() return now end
function ShadowCandidate(candidate, kind, text_value, comment)
  return { text = text_value, type = kind, comment = comment,
    start = candidate.start, _end = candidate._end, quality = candidate.quality }
end

local ctx = { input = "gongshi", caret_pos = 7 }
function ctx:is_composing() return true end
local waiting_env = {
  ai_enabled = true, ai_auto = true, ai_wait = true, ai_dir = "mock",
  ai_state = { id = "waiting", context = "", generation = 0, last = now },
  engine = { context = ctx },
}
local function render(variant)
  files["focus.txt"] = focus_token .. "\n" .. tostring(now) .. "\n"
  output = {}
  local input, state = translation(9)
  for _, candidate in ipairs(state.candidates) do
    candidate.start, candidate._end = 0, 7
  end
  if variant == "partial" then
    for i = 2, 4 do state.candidates[i]._end = 3 end
  elseif variant == "short" then
    for i = 2, 4 do state.candidates[i].text = "短" end
  end
  module.filter.func(input, waiting_env)
  return state
end
function ctx:refresh_non_confirmed_composition() render(); return true end
render()
assert(#output == 0 and waiting_env.ai_state.waiting, "Pending candidates must stay hidden")
assert(not files["applied.tmp"], "Pending result must not be acknowledged")
local first_id = waiting_env.ai_state.request_id
files["response.txt"] = first_id .. "\n2,1,3,4,5,6,7,8\n"
render()
assert(#output == 9 and output[1].text == "candidate-2", "Ready order/tail must appear together")
assert(output[1].comment:find("[AI]", 1, true), "Ready result should carry AI marker")
assert(files["applied.tmp"] == first_id .. "\n" .. "ai\n", "AI result acknowledgement missing")
now = now + 5
render()
assert(output[1].text == "candidate-2", "Resolved result must not revert on elapsed time")

ctx.input, ctx.caret_pos = "gongshix", 8
render()
assert(#output == 9 and output[1].text == "candidate-2", "Matching semantic result should avoid another wait")
waiting_env.ai_state.context = "changed context"
render()
assert(#output == 0, "Changed context must not reuse a cached result")
local timeout_id = waiting_env.ai_state.request_id
files["timeout.txt"] = timeout_id .. "\n"
render()
assert(#output == 9 and output[1].text == "candidate-1", "Timeout must reveal original order")
assert(files["applied.tmp"] == timeout_id .. "\noriginal\n", "Fallback acknowledgement missing")
files["response.txt"] = timeout_id .. "\n2,1,3,4,5,6,7,8\n"
render()
assert(output[1].text == "candidate-1", "Late result must not cause another jump")

ctx.input, ctx.caret_pos = "gongshiy", 8
render()
assert(#output == 0, "Next input should wait again")
local enter = {
  keycode = 0xff0d, release = function() return false end,
  ctrl = function() return false end, shift = function() return false end,
  alt = function() return false end, super = function() return false end,
}
assert(module.processor.func(enter, waiting_env) == 2, "Enter must continue to normal editor")
assert(#output == 9 and output[1].text == "candidate-1", "Enter must restore candidates first")

ctx.input = "gongshiz"
waiting_env.ai_auto = false
render()
assert(#output == 9, "Manual-only mode must not hide the candidate table")
waiting_env.ai_auto = true
focus_token = "another-control"
render()
assert(waiting_env.ai_state.context == "", "Focus change must clear stale history")
assert(#output == 0, "Focus change must clear semantic cache")
local last_request = files["request.tmp"]
ctx.input = "different-spans"
-- Use a valid alphabet input while modifying actual candidate coverage.
ctx.input = "gongshia"
render("partial")
assert(#output == 9, "Only one comparable candidate must not hide the table")
assert(files["request.tmp"] == last_request, "Ineligible input must not write a request")
ctx.input = "gongshib"
render("short")
assert(#output == 9, "Different character lengths must not hide the table")
assert(files["request.tmp"] == last_request, "Length mismatch must not write a request")
focus_token = "third-control"
ctx.input = "gongshic"
render()
local invalid_id = waiting_env.ai_state.request_id
files["response.txt"] = invalid_id .. "\n1,2,3,4,5,6,7,8,999\n"
render()
assert(#output == 9 and output[1].text == "candidate-1", "Extra response indices must be rejected")
ctx.input = "gongshid"
render()
assert(#output == 0, "Invalid response must not be cached")
local pending_id = waiting_env.ai_state.request_id
files["response.txt"] = pending_id .. "\n2,1,3,4,5,6,7,8\n"
render()
ctx.input = "gongshie"
render()
assert(#output == 9 and output[1].text == "candidate-2", "Semantic cache should be reused")
local cached_id = waiting_env.ai_state.request_id
local old_request = files["request.tmp"]
render()
assert(waiting_env.ai_state.request_id == cached_id and files["request.tmp"] == old_request,
  "Cache hits must not create a worker request")
-- Changing candidate order must miss even though the same words remain available.
waiting_env.ai_state.context = "new history"
render()
assert(#output == 0, "New history must invalidate cached selection")
io.open, os.remove, os.rename, os.time = old_open, old_remove, old_rename, old_time
ShadowCandidate = old_shadow
print("PASS: hidden pending/ready/stale/timeout/late result/Enter/manual mode")
