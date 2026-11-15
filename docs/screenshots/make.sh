#!/bin/bash
# Retakes the screenshots in this folder from the saved interview in results/traces/. No model is needed.
# Needs: `python3 app.py` running, Google Chrome and ImageMagick. Written for macOS.
set -e
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PAGE="http://localhost:8000/?trace=storyboard-interview&w=300&step"
PROFILE="$(mktemp -d)"

shot() {  # file name, height in px, step and what to show
  "$CHROME" --headless=new --hide-scrollbars --force-device-scale-factor=3 --window-size=500,"$2" \
    --virtual-time-budget=4000 --user-data-dir="$PROFILE" --screenshot="$1.png" "$PAGE=$3" >/dev/null 2>&1
  # Chrome's window cannot be narrower than 500 px, so the 300 px page is cut out of the middle.
  magick "$1.png" -gravity center -crop "900x$(($2 * 3))+0+0" +repage -strip "$1.png"
  echo "$1.png"
}

shot start          620 "0"

# Storyboard 1, question 1: thinking aloud, a question about a term, then the answer.
shot 1a-thinking    560 "2"
shot 1b-question    560 "3&top=turn"
shot 1c-answer      560 "4&top=turn"

# Storyboard 2, question 4: the two readings disagree, TurnCheck asks, then gives the no-hints reply.
shot 2a-sent        600 "11&pending=1&top=divider"
shot 2b-asked       600 "11&top=divider"
shot 2c-no-hints    600 "12&top=turn"

# Storyboard 3, question 3: a request recorded as the answer (a miss found by the stress turns),
# taken back with one tap after TurnCheck had moved on; then the record.
shot 3a-misread     660 "8"
shot 3b-corrected   660 "9&top=turn"
shot 3c-record      660 "14&row=3"
