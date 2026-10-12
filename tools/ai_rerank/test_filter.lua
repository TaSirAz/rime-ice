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
