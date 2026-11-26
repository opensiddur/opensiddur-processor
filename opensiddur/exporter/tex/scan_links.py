"""Lua margin-marker placement, embedded in the LuaLaTeX preamble.

All coordinates are scaled points from zref's previous pass. Moving a zero-size
marker box never changes paragraph wrapping. Fallback stays within two symbol rows
of the source baseline and inside the text area. Unknown first-pass positions are
ignored; absolute pages distinguish books which restart their printed counters.
"""

MARGIN_PLACEMENT_LUA = r"""
OSScanLinks = {pages = {}}
function OSScanLinks.place(page, edge, y, left, paperwidth, paperheight,
                           width, height, depth, separation, gap, bottom, top)
  if page == 0 or y == 0 then return 0, 0 end
  local placed = OSScanLinks.pages[page] or {}
  OSScanLinks.pages[page] = placed
  local room = left and edge or (paperwidth - edge)
  local lanes = math.floor((room - separation - gap) / (width + gap))
  local step = height + depth + gap
  bottom = bottom or gap
  top = top or (paperheight - gap)
  local rows = 2
  for row = 0, rows do
    local shifts = row == 0 and {0} or {-row * step, row * step}
    for _, dy in ipairs(shifts) do
      for lane = 0, lanes - 1 do
        local dx = lane * (width + gap)
        local x = left and (edge - separation - dx - width)
                       or (edge + separation + dx)
        local box = {x, y + dy - depth, x + width, y + dy + height}
        local free = box[1] >= gap and box[3] <= paperwidth - gap
                 and box[2] >= bottom and box[4] <= top
        for _, other in ipairs(placed) do
          if box[1] < other[3] + gap and box[3] + gap > other[1]
             and box[2] < other[4] + gap and box[4] + gap > other[2] then
            free = false
            break
          end
        end
        if free then
          table.insert(placed, box)
          return dx, dy
        end
      end
    end
  end
  error("Source-link margin full on physical page " .. page ..
        ": use inline scan links or a smaller symbol")
end
"""
