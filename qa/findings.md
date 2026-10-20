# Open problems

- **"윤슬아 여기서 기다려" ("Yunseul, wait here") → skips the scene.** The decision model is confident in `cut` at 0.91. The same goes for the three sentences in the casual-speech set that ask someone to stay. Requiring both models to agree on `cut` fixes it, but then "우리 같이 기다리자" ("let's wait together") reads as talk, so the gains and losses even out and it was left as is (qa_test/runs/misread-1/REPORT.md).
- **"부두로 간다" ("go to the pier", while at 선착장) → "이미 선착장에 있습니다".** Another name for the same place is read as the current place (misread-1).
- **"바다 쪽으로 내려간다" ("head down toward the sea", from the village) → in front of the lighthouse.** The move card lets you pick 선착장, so you never end up in the wrong place (move-1 turn 7).
- **A cancelled card's sentence stays in the chat.** Closing the move card and sending the same sentence again shows the same bubble twice (move-1 turns 2–3).

## From playtest round 0 (one `talker` game, `qa_test/runs/play-0-talker`, played through `qa/play/play.py`)

- **A companion named in an action on a thing becomes its target.** "윤슬에게 '이제 같이 밀어요!' 하며 문을 연다" and "둘이 함께 어깨로 문을 들이받는다" opened a roll card for "윤슬에 완력으로 맞선다" (turns 26, 30). Both times the card had to be cancelled.
- **The narration runs ahead of a move card.** For "…하고 바닷가 마을로 간다" the first step was read as talking. That step's narration already walked into the village, but the move card was still open and the player had not moved (turns 9, 20).
- **Companions drop at a place they avoid, with no reason given.**
  - "도해는 남음" one command after 도해 agreed to come (turn 20). "윤슬은 남음" on the way to the lamp room (turn 37).
  - The narration still puts 윤슬 in the lamp room after she stayed behind (turn 38).
  - The move card shows who stays, but not why, and offers no way to bring them.
- **A person's shown attitude reads as their mood.** 윤슬 is "무덤덤" (trust and fear 0) the whole game, yet speaks with "우와", "눈을 반짝이며" every turn (turns 3–34).
- **It is invisible which actions spend time.** One chat moved 해가 진다 to 3/3 and ended chapter 1 on its deadline (turn 24). Earlier chats cost nothing. The failed deadline then passed into chapter 2 with fresh clocks and nothing else to mark it.
- **Recaps contradict the screen and the narration.**
  - The chapter 1 recap says "당신은 홀로 등대 앞에 서 있습니다" while 윤슬 is with you (turn 24).
  - The chapter 2 recap says the lamp "희미하게 숨을 틉니다" right after the ending narration said it shines "눈부시게" (turn 46).
- **A roll card offers two options with the same name.** "기름통" appears twice: one is the thing (`thing:oil`), the other is what you know about it (`prop:oil.hidden`) (turns 39, 41, 45).
- **A known way cannot be used.**
  - "무너진 담장을 기어올라 아래층 창문으로 들어간다" was refused with "이미 등대 앞에 있습니다" (turn 23).
  - Sentences about going to the wall were read as asking 윤슬 about it again (turns 9, 22).
- **A sentence close to a button's label became another solution of the same obstacle.** "기름통에 남은 기름을 전부 등불에 들이붓는다" was read as "렌즈를 닦고 불씨를 살린다" rather than the button "기름을 모두 등불에 붓는다" (turn 41).
- **The ending picks up none of what the player built.** It does not mention the son's letter that won 도해 over (turns 18–19), the debt to 도해, or either companion (turn 46).
