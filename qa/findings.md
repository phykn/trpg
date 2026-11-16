# Open problems

Each with its evidence (`qa_test/runs/<run>`, turn numbers).

## The text check misses a changed meaning

`qa_test/runs/text-dawn-3/results.json`, case `말 브람.징수관.깨진 뒤`: gemma4 wrote "그건 모르겠소. 나는 이제 장부를 맞추러 촌장 댁에 가봐야 하니, 이 가방 좀 맡아주시오." It drops the bribe and turns the collector's errand into 브람's, yet Kanana's meaning check gave 0.84. The line's "그는" is easy to misread. The notebook keeps the true line, so the deduction is not lost, but the spoken answer misleads. The real UI shows it every time: `qa_test/runs/ui-t13-1`, turn 7 at all three widths ("제가 장부를 맞추러 촌장 댁에 가야 하니 이 가방 좀 맡겨 두겠소" at 320 and 412; the errand and the bag left out at desktop). The AI testers met it again (`qa_test/runs/qa-1` turn 40, `qa-2` turn 30). The line now names the collector as the one who leaves the bag ("징수관은 … 내게 가방을 맡겼다"); replay it, and if it still flips, add a check that compares who does what.

## 브람's "~소" lands on other endings

`qa_test/runs/ui-t13-1`, turn 4 at all three widths: "징수관은 우리 여관에 오지도 않았다소." The bio says he ends with "~소"; gemma4 glues it onto "-았다" despite the rule to write grammatical Korean. Try the bio's wording (an example sentence such as "왔소", "없소") or a grammar check.

## The ending text adds or bends facts

`qa_test/runs/ui-t14-1`: at 412, turn 27, the passage says "당신이 짚은 사람이 끌려가고" and gemma4 wrote "당신이 지목한 남자가" for 넬, a woman. At desktop, turn 11, the truth says the neck mark came from the cart rope; the ending calls it "범행의 흔적일 뿐". In `qa_test/runs/play-t15-1`, turn 9, it called 고드릭 "탐욕스러운 영주"; he is the village head. The ending is checked like a scene, so none was caught. Try naming the accused in the ending job, and a check against the truth text.

## Interpretation misses on the held-out set

Asks are now written by the rules of game/08 4절, and players' sentences sit apart in `evals-held.yaml` (`qa_test/runs/evals-rule-*`). Working and held-out: 프롤로그 87% and 87%, 챕터 1 93% and 81%, Dev 82% on 11 working cases. Only the 프롤로그 working set has a wrong topic: "어디 계셨어요? 매표소에 계셨어요?" read as two topics, the second at 0.05. Left on 챕터 1's held-out set: a name the model cannot tie to its topic ("에드윈" for 징수관), back-questions between near topics (마렌's 마당 and 아버지의 저녁, 넬's 독미나리 and 시신), and chat or a plain question read as 넘김. Do not fit asks to these sentences; a fix has to be a rule that holds for every story. In `qa-1` turns 25–27 토빈 asked the same back-question after the player picked one; a back-question that remembers the pick is still open.

## Narration places things where the notebook does not

A scene with many new lines now draws only two or three, where the notebook puts them; on the forest road three runs out of three matched (gemma4 directly, before and after). Left: `qa-2` turns 25, 33, the chimney-smoke omen is gone from the next scene of that house, and `qa-5` turn 60 "아무런 기척도 … 이곳에는 고드릭과 마렌이 있습니다". Replay a full game to see whether placements still slip.

## Answers take the player's premise as fact

`qa-6` turn 9 ("어젯밤에 기도했다면서"), `qa-5` turn 73, `qa-3` turn 24. With the rule to ask back instead, gemma4 asked back in three of four tries ("그건 누가 그러더냐?") and still once went on to pray for the village. Same family as adding facts.

## Speech drifts

`qa-1`: 브람 "않았다요", 넬 "내놓기나 해", 고드릭 between 하게체 and 합니다체; `qa-2` turns 5–7, 40. 고드릭 called an ordinary question "무례한" (`qa-1` turns 2–3), when the intro did not yet say the dead man was the lord's collector.

## Questions for the playtest (T16, T17)

Not bugs; the testers' play raises them and a person should judge them.
- The omen comes three cells early, but the walk there can take two or three (`qa-5` turns 37–38: the smoke led to ashes). Is three cells enough to act on?
- A failed roll closes that way and lowers the others with no reason shown (`qa-5` turns 63, 66).
- The ending is told at the hour the cells run out, not when the player concluded (`qa-5`, `qa-6`: "새벽 4시").
