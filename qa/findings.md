# Open problems

- **"윤슬아 여기서 기다려" ("Yunseul, wait here") → skips the scene.** The decision model is confident in `cut` at 0.91. The same goes for the three sentences in the casual-speech set that ask someone to stay. Requiring both models to agree on `cut` fixes it, but then "우리 같이 기다리자" ("let's wait together") reads as talk, so the gains and losses even out and it was left as is (qa_test/runs/misread-1/REPORT.md).
- **"부두로 간다" ("go to the pier", while at 선착장) → "이미 선착장에 있습니다".** Another name for the same place is read as the current place (misread-1).
- **"바다 쪽으로 내려간다" ("head down toward the sea", from the village) → in front of the lighthouse.** The move card lets you pick 선착장, so you never end up in the wrong place (move-1 turn 7).
- **A cancelled card's sentence stays in the chat.** Closing the move card and sending the same sentence again shows the same bubble twice (move-1 turns 2–3).
- **A companion staying behind at a place it avoids has not been seen on screen.** Only checked by a rule test (`test_a_companion_goes_along_until_a_place_it_avoids`).
