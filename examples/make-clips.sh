#!/bin/sh
# Narrate muon-zh.json with macOS's built-in Chinese voice. The clips are
# written next to this script and are not part of the repository.
set -e
cd "$(dirname "$0")"
say -v Tingting -o 1.aiff "宇宙射线撞上大气层，会产生大量缪子。"
say -v Tingting -o 2.aiff "缪子比电子重得多。"
say -v Tingting -o 3.aiff "所以它能穿透很厚的岩石。"
echo "wrote 1.aiff 2.aiff 3.aiff; now run: tts-asr-check check muon-zh.json"
