# Open problems

Each with its evidence (`qa_test/runs/<run>`, turn numbers).

## The text check misses a changed meaning

`qa_test/runs/text-dawn-3/results.json`, case `말 브람.징수관.깨진 뒤`: gemma4 wrote "그건 모르겠소. 나는 이제 장부를 맞추러 촌장 댁에 가봐야 하니, 이 가방 좀 맡아주시오." It drops the bribe and turns the collector's errand into 브람's, yet Kanana's meaning check gave 0.84. The line's "그는" is easy to misread. The notebook keeps the true line, so the deduction is not lost, but the spoken answer misleads. The real UI shows it every time: `qa_test/runs/ui-t13-1`, turn 7 at all three widths ("제가 장부를 맞추러 촌장 댁에 가야 하니 이 가방 좀 맡겨 두겠소" at 320 and 412; the errand and the bag left out at desktop). The AI testers met it again (`qa_test/runs/qa-1` turn 40, `qa-2` turn 30). The line now names the collector as the one who leaves the bag ("징수관은 … 내게 가방을 맡겼다"); replay it, and if it still flips, add a check that compares who does what.

## 브람's "~소" lands on other endings

`qa_test/runs/ui-t13-1`, turn 4 at all three widths: "징수관은 우리 여관에 오지도 않았다소." The bio says he ends with "~소"; gemma4 glues it onto "-았다" despite the rule to write grammatical Korean. Try the bio's wording (an example sentence such as "왔소", "없소") or a grammar check.

## The ending text adds or bends facts

`qa_test/runs/ui-t14-1`: at 412, turn 27, the passage says "당신이 짚은 사람이 끌려가고" and gemma4 wrote "당신이 지목한 남자가" for 넬, a woman. At desktop, turn 11, the truth says the neck mark came from the cart rope; the ending calls it "범행의 흔적일 뿐". In `qa_test/runs/play-t15-1`, turn 9, it called 고드릭 "탐욕스러운 영주"; he is the village head. The ending is checked like a scene, so none was caught. Try naming the accused in the ending job, and a check against the truth text.

## An answer can drop half of its line

`qa_test/runs/newbie-1`, turn 2: 최두식 said only "벨트는 6시까지 케이스에 있었다", while the notebook wrote the whole line with "강태오가 제일 수상하다" and added 강태오. Kanana's meaning check passed it. Same family as the first finding. `qa_test/runs/qa-2`, turn 27: two topics asked at once, one answered aloud, both written. `qa-5` turn 46: 마렌 says only "그건... 제가 잘 모르겠어요..." as her lie breaks, while the notebook writes her confession.

## Back-questions between two near topics

`qa_test/runs/evals-arena`: 83% against the 85% bar. Both misses are back-questions between 최두식's 벨트 and 그 시각 ("누가 가져간 것 같아요?", "벨트 없어질 때 실장님은 뭐 하고 계셨어요?"); none went to a wrong topic. Before the asks were widened, `qa-3` turns 14 and 16 ("어디 계셨어요?") fell through to no topic, so the lie could not be heard. In `qa-1` turns 25–27 토빈 asked "숲길에서 본 것인가요, 사당에서 본 것인가요?" again after the player picked one. Try a back-question that remembers the pick, or clearer topic names.

## Narration places things where the notebook does not

`qa-6` turn 26: the order is "허리띠에" in the scene, "품에" in the notebook. `qa-5` turn 60: "아무런 기척도 … 이곳에는 고드릭과 마렌이 있습니다". `qa-1` turn 20 and `qa-2` turn 12: the wooden tag is "품에" in the scene, "허리띠에" in the notebook. `qa-2` turns 18, 25: "당신의 손에는 쇠꼬챙이가 들려 있습니다" for a thing only seen. `qa-2` turns 25, 33: the chimney-smoke omen is gone from the next scene of that house. Try giving the scene the written lines' own words and a check for things held or moved.

## Answers take the player's premise as fact

`qa-6` turn 9: 고드릭 takes up a made-up "어젯밤에 기도했다면서". `qa-5` turn 73: "어젯밤에 술을 한잔 냈을 때", the wrong night and a cup nowhere in the notebook. `qa-3` turn 24: shown the trunk, 강태오 says "그게 왜 내 트렁크에서 나와야 하냐고" though nothing says it is his. Same family as adding facts.

## The ending lists lies and held topics never met

`qa-5` turn 76 lists 넬's held topic though it never showed in play. `qa-1` turn 57, `qa-2` turn 56: "깨지 못한 거짓말" names lies the player never heard, and 에드윈's name first appears there. Decide whether the ending shows only heard lies, or says where each could have been heard.

## Speech drifts

`qa-1`: 브람 "않았다요", 넬 "내놓기나 해", 고드릭 between 하게체 and 합니다체; `qa-2` turns 5–7, 40. 고드릭 called an ordinary question "무례한" (`qa-1` turns 2–3), when the intro did not yet say the dead man was the lord's collector.

## Questions for the playtest (T16, T17)

Not bugs; the testers' play raises them and a person should judge them.
- One fact breaks a lie. 고드릭's "멀쩡히 걸어 나갔다" falls only to 밤에 나간 수레; a detective presented the dry boots, the lips and the cart tracks first and got "무슨 상관" each time (`qa-5` turns 54, 70, 71).
- The omen comes three cells early, but the walk there can take two or three (`qa-5` turns 37–38: the smoke led to ashes). Is three cells enough to act on?
- The same wrong present costs a cell every time, with nothing to say it was tried (`qa-6` turns 9, 10). A failed roll closes that way and lowers the others with no reason shown (`qa-5` turns 63, 66).
- A blank conclusion is accepted at once (`qa-6` turn 35, shell); check that the phone's sheet asks first.
- The ending is told at the hour the cells run out, not when the player concluded (`qa-5`, `qa-6`: "새벽 4시").
