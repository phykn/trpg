# Open problems

Each with its evidence (`qa_test/runs/<run>`, turn numbers).

## The text check misses a changed meaning

`qa_test/runs/text-dawn-3/results.json`, case `말 브람.징수관.깨진 뒤`: gemma4 wrote "그건 모르겠소. 나는 이제 장부를 맞추러 촌장 댁에 가봐야 하니, 이 가방 좀 맡아주시오." It drops the bribe and turns the collector's errand into 브람's, yet Kanana's meaning check gave 0.84. The line's "그는" is easy to misread. The notebook keeps the true line, so the deduction is not lost, but the spoken answer misleads. The real UI shows it every time: `qa_test/runs/ui-t13-1`, turn 7 at all three widths ("제가 장부를 맞추러 촌장 댁에 가야 하니 이 가방 좀 맡겨 두겠소" at 320 and 412; the errand and the bag left out at desktop). The AI testers met it again (`qa_test/runs/qa-1` turn 40, `qa-2` turn 30). The line now names the collector as the one who leaves the bag ("징수관은 … 내게 가방을 맡겼다"); replay it, and if it still flips, add a check that compares who does what.

## 브람's "~소" lands on other endings

`qa_test/runs/ui-t13-1`, turn 4 at all three widths: "징수관은 우리 여관에 오지도 않았다소." The bio says he ends with "~소"; gemma4 glues it onto "-았다" despite the rule to write grammatical Korean. Try the bio's wording (an example sentence such as "왔소", "없소") or a grammar check.

## The ending text adds or bends facts

`qa_test/runs/ui-t14-1`: at 412, turn 27, the passage says "당신이 짚은 사람이 끌려가고" and gemma4 wrote "당신이 지목한 남자가" for 넬, a woman. At desktop, turn 11, the truth says the neck mark came from the cart rope; the ending calls it "범행의 흔적일 뿐". In `qa_test/runs/play-t15-1`, turn 9, it called 고드릭 "탐욕스러운 영주"; he is the village head. The ending is checked like a scene, so none was caught. Try naming the accused in the ending job, and a check against the truth text.

## Interpretation misses on the held-out set

After the asks rules and the new kind, two and second questions (engine/01 1절; `qa_test/runs/evals-tks-*`): working 90%, 92%, 93% with no wrong topics; held-out 프롤로그 87%, 챕터 1 81%, no wrong topics, unchanged by the fixes. Left, all needing knowledge of the story: a name heard in the intro ("에드윈에 대해 아는 것을…" to 고드릭), "여기" meaning the topic's place (토빈 "여기서 뭘 봤어?", 윤소라 "최 실장님이 오늘 여기 왔었나요?"), near topics (넬's 독미나리 and 시신, 마렌's 마당 and 아버지), and chat against 넘김. Putting the place or the intro in the situation, and adding asks by name, each did worse. The repeated back-question of `qa-1` turns 25–27 no longer happens: those sentences now read as 사당 with no context.

## Narration places things where the notebook does not

A scene with many new lines now draws only two or three, where the notebook puts them; on the forest road three runs out of three matched (gemma4 directly, before and after). Left: `qa-2` turns 25, 33, the chimney-smoke omen is gone from the next scene of that house, and `qa-5` turn 60 "아무런 기척도 … 이곳에는 고드릭과 마렌이 있습니다". Replay a full game to see whether placements still slip. `research5-text-dawn` 촌장 집: "넓은 마당 끝에 묵직한 장부 궤짝이" puts the chest in the yard.

## Answers take the player's premise as fact

`qa-6` turn 9 ("어젯밤에 기도했다면서"), `qa-5` turn 73, `qa-3` turn 24. With the rule to ask back instead, gemma4 asked back in three of four tries ("그건 누가 그러더냐?") and still once went on to pray for the village. Same family as adding facts.

## Speech drifts

`qa-1`: 브람 "않았다요", 넬 "내놓기나 해", 고드릭 between 하게체 and 합니다체; `qa-2` turns 5–7, 40. 고드릭 called an ordinary question "무례한" (`qa-1` turns 2–3), when the intro did not yet say the dead man was the lord's collector.

## Answers rarely react to what the person watched

`react-witness-3` turns 4–5: 최두식 got "이곳을 둘러봤다" both in 받은 것 and next to the player's line, and still answered as if nothing happened. Not yet tried with opening a lock or presenting to someone else in front of them.

## A pass flags "할 말" as prompt words

`react-text-2` 넘김 넬: "모르니까 그냥 가. 할 말 없으니." fails `prompt` twice, though "할 말 없다" is ordinary speech.

## Chat that drifts into a case question

`react-evals-arena`: "벨트 없어질 때 실장님은 뭐 하고 계셨어요?" became 잡담 (was 되묻기) once requests, griping and jokes joined 잡담. `react-replay-2` turn 13: "아까 대기실 앞에서 누구 못 봤어?" to 강태오 was read as looking, though the evals with a full notebook pass it.

## Impressions that overlap

`impress-held-dawn`: "독초를 다룰 줄 아십니까?" to 넬 gave her own 약초 (an unlock) though it asks about poison; `impress-evals-dawn`: "할멈, 약초 다루는 솜씨가 대단하다고 들었소" gave the common 칭찬 instead of 약초. Threats that accuse now leave 위협 (위협 ≥ 0.3 outranks a top 의심; arena wrong impressions 2 → 0, `research5-evals-arena`). Dawn still misses the 5% goal by one sentence: "징수관이 해 질 녘에 여기 왔소?" reads as 의심 (0.51), and 넬's own 약초 loses to the common 칭찬 (0.79 against 0.15) because 칭찬 already covers praising a skill. Rewording 약초 twice changed nothing, so 넬's own 약초 is gone and 시신 opens with 칭찬.

## Questions for the playtest (T16, T17)

Not bugs; the testers' play raises them and a person should judge them.
- The omen comes three cells early, but the walk there can take two or three (`qa-5` turns 37–38: the smoke led to ashes). Is three cells enough to act on?
- A failed roll closes that way and lowers the others with no reason shown (`qa-5` turns 63, 66).
- The ending is told at the hour the cells run out, not when the player concluded (`qa-5`, `qa-6`: "새벽 4시").

## A told plea with nothing else to go on is missed

`qa_test/runs/research5-evals-dawn`: "부탁이오, 하고 넬에게 고개를 숙인다" reads as 넘김 with no button: the action option is 0.14 and the told-deed question 0.77, under its 0.8. The told-deed question alone no longer offers buttons: it gave 0.6–0.74 to plain questions ("창문은 누가 열었어요?"), and nine of the ten buttons it raised were on non-actions (`research-held-arena`, five of fifteen plain questions). Actions overall: 75/78.

## A topic and a move that tie

`research5-evals-dawn`: "촌장 집에 가 봐야겠소." to 브람 reads as 넘김: topic 0.42, move 0.40 (the topic question says none). Dawn's original topic sentences are one under `impress-evals` because of it. Not taken as a move on a tie, since a wrong move spends a cell and a wrong pass costs nothing.

## A threat built on a bluff reads as deceit

`qa_test/runs/research-dawn` turn 24: "계속 거짓말하면 영주님 기사들한테 당신 장부부터 넘기겠소." (the player has no ledger) became 속인다 (0.51, and 0.63 after 몰아세운다 got "윽박지른다"). The impression was 위협. Both readings are defensible; a playtest should say which the player meant.

## Conjugation slips in narration

`research-dawn` turn 10: "말린 풀 다발을 뒤집어 건습니다" for 겁니다 (걸다). The 해라체 of a story's doing sentence is now caught and rewritten (`research5-text-dawn`, 오두막), but a wrong 합니다체 form is not checked.

## The pass check flags 토빈's plain pass

`research5-text-dawn` 넘김 토빈: "무서운 걸 물으시네요, 전 그런 건 잘 몰라요." fails `added` on all three tries though it adds nothing. Seen before this work too (`impress-text-dawn`).
