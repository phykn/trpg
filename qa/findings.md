# Open problems

- **Sentences read as skipping the scene, and the skip runs with no card.**
  - "윤슬아 여기서 기다려" ("Yunseul, wait here"): the decision model is confident in `cut` at 0.91, and so are the three sentences in the casual-speech set that ask someone to stay. Requiring both models to agree on `cut` fixes it, but then "우리 같이 기다리자" ("let's wait together") reads as talk. The gains and losses even out, so it was left as is (qa_test/runs/misread-1/REPORT.md).
  - "…기름통 챙기고 누렁이 쓰담쓰담" ("pet the dog") became `cut` as its second step. The sunset ran out and chapter 1 failed while the narration showed the petting (play-2-odd 33).
  - A skip spends the rest of the scene, yet a sentence reaches it with no confirm card.
- **"부두로 간다" ("go to the pier", while at 선착장) → "이미 선착장에 있습니다".** Another name for the same place is read as the current place (misread-1).
- **"바다 쪽으로 내려간다" ("head down toward the sea", from the village) → in front of the lighthouse.** The move card lets you pick 선착장, so you never end up in the wrong place (move-1 turn 7).
- **A cancelled card's sentence stays in the chat.** Closing the move card and sending the same sentence again shows the same bubble twice (move-1 turns 2–3).

## From playtests (round 1: `play-1-*`; round 2: `play-2-explorer`, `-talker`, `-bold`, `-odd`; real UI `ui-3`, `ui-4`)

Each item showed up in two or more games or blocked one. Round 1 ran on ca504938, and round 2 on the fixes after it, both with seeds 11–14. Round 2 scores and what the fixes changed are in `qa_test/runs/play-2-summary.md`.

- **A companion's fear cannot be overcome, and "bring X" in a move sentence is dropped.**
  - The move card now gives the reason ("도해는 남음: 등대에 다시 오르는 것을 두려워합니다"), and no round-2 game narrated an absent companion as present.
  - Winning a roll to calm 도해's fear and his own "약속했으니, 가야겠네" still left him behind (play-2-talker 29, 32, 35, 36).
  - "윤슬이 데꼬 등대앞 가서" and "도해 아재랑 누렁이 데꼬" opened a move card with no one to bring and no reason (play-1-odd 5, play-2-odd 35).
  - "문 앞까지만 같이 가 주세요" was read as asking him to wait here (play-2-talker 31).
- **Oil sentences reach the fork only as a second step.** "기름은 등잔에 다 부어" and "…등불에 기름을 붓는다" became the lens roll followed by "→ 다음: 갈림길에서 하나를 고른다", a label that reads as a placeholder (play-2-odd 46, play-2-talker 43). Pouring oil on the hinges became a shoulder charge (play-2-explorer 25).
- **Showing a thing hands it over, with no card.** "편지 보여주고" gave the letter to 윤슬 and it could not be taken back (play-2-odd 3, 5, 6). "보여 준다" also became giving at play-2-talker 25.
- **What to lean on reads as arbitrary.**
  - "기름통" is listed twice with the same numbers: once as the thing and once as what you know about it (play-1-talker 39; play-2-explorer 25, 27, 37; play-2-talker 43, 47; play-2-odd 44, 49).
  - The obstacle itself is offered as help against itself (play-1-talker 11–12; play-2-odd 29).
  - A clue the player earned is worth the same as any other help (play-2-explorer 23), and a trait offered once is gone later with no reason (play-2-explorer 14, 42; play-2-bold 3).
- **The shown attitude reads as the person's mood.** 윤슬 is "무덤덤" all game but speaks "들뜬 목소리로", "눈을 반짝이며" or "떨리는 목소리로" (every game in both rounds; play-2-explorer 1–6, play-2-talker 3–4, play-2-odd 1, 3). 도해 at 무덤덤 speaks "겁에 질린 눈으로" (play-2-talker 19).
- **A failed chapter goal still feels free.**
  - The next deadline now starts one box filled, and the change line says the goal was missed (play-2-explorer 33).
  - Testers still saw no cost (play-2-explorer 33, play-2-talker 27, play-2-odd 33). The narration never mentions the missed sunset. A success can land in the same step as the failure (play-2-explorer 33).
  - Which looks cost daylight is not visible (play-2-explorer 9, 18; play-2-talker 17).
- **A roll card's failure cost leaves things out.** The card shows one clock, but the scene-end ticks and new marks come too: four clocks moved at play-2-bold 9, and a 불리함 the card never named appeared at play-2-bold 13. A full clock striking and resetting showed only as a line (play-2-bold 23, play-2-odd 50; the wording is fixed since).
- **Moves toward something in the same place are refused with an unrelated reason.** "이미 … 에 있습니다" answered crossing the bridge, flying to the lamp room and the wall route (play-1-explorer 10, 27; play-1-odd 10; play-2-odd 12, 19). The known wall route never becomes a way in (play-1-talker 23; play-2-explorer 29).
- **The refusal "지금은 할 수 없는 행동입니다" gives no reason.** It answered taking a rope in the scene, knocking on a door, calling out across the yard, using a trait to remember, and climbing the stairs to an open room (play-2-explorer 3; play-2-talker 20, 40; play-2-odd 5, 10, 18, 22, 28; play-1-bold 14).
- **Obstacle wording leaks into the narration.** "꽉 조여져 있던 꺼진 등불이 조금 풀리며" (play-2-explorer 38), "풀려버린 누렁이" (play-2-odd 30), as in play-1-bold 21 and play-1-talker 14.
- **The narration runs ahead of the clocks.**
  - Narration bench weather per turn fell from 2.63 to 1.80 (`narr-2/base-1` → `narr-2/fix-3`).
  - Still, a ship hits the reef at 1/3 or 2/3 (play-2-talker 27, play-2-explorer 38, play-2-odd 38), and the sky darkens on turns where no clock moved (play-2-explorer 11, 13, 28; play-2-odd 17).
  - In the bench, the decision model's check called 9 sentences contradictions against 1 before. They were mostly calm-sea dialogue under an approaching storm, and the final texts kept their quotes (`narr-2/fix-3`).
- **The narration runs ahead of the screen.** The flame lights while 꺼진 등불 is 0/4 (play-2-bold 6–7). Oil is poured onto the lens on the move into the room (play-2-odd 44). Taking the oil can became looking at it while the narration had it taken (play-2-explorer 16).
- **Chapter recaps contradict the screen.** The player is put on the lighthouse stairs while in the village (play-2-talker 27). The rain drives away the darkness (play-2-talker 48). The sun is said to fail the goal (play-2-odd 33). Round 1: play-1-explorer 28, 43; play-1-bold 29; play-1-odd 29.
- **Chapter 2 is the same roll over and over.** Wiping the lens, pouring oil and aiming the lens all become "렌즈를 닦고 불씨를 살린다" (play-2-explorer 37–41; play-2-bold 8–25). Failures stack 불리함 (play-1-bold 13–25).
- **The second half of a two-action sentence is dropped** (play-2-odd 11, 25; play-2-explorer 20).
- **A clock or obstacle outlives what the narration did to it.** The bridge was swept away but is still listed (play-2-talker 37). 무너지는 다리 and 남은 기름 disappeared with no narration (play-1-talker 44; play-1-bold 11).
- **A companion named in an action on a thing becomes its target.** "윤슬에게 '이제 같이 밀어요!' 하며 문을 연다" opened "윤슬에 완력으로 맞선다" (play-0-talker 26, 30). "편지를 쥔 채 … 불을 당긴다" made the letter the target (play-2-bold 20).
