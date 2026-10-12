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
