# Open problems

Each with its evidence (`qa_test/runs/<run>`, turn numbers).

## The text check misses a changed meaning

`qa_test/runs/text-dawn-3/results.json`, case `말 브람.징수관.깨진 뒤`: gemma4 wrote "그건 모르겠소. 나는 이제 장부를 맞추러 촌장 댁에 가봐야 하니, 이 가방 좀 맡아주시오." It drops the bribe and turns the collector's errand into 브람's, yet Kanana's meaning check gave 0.84. The line's "그는" is easy to misread. The notebook keeps the true line, so the deduction is not lost, but the spoken answer misleads. The real UI shows it every time: `qa_test/runs/ui-t13-1`, turn 7 at all three widths ("제가 장부를 맞추러 촌장 댁에 가야 하니 이 가방 좀 맡겨 두겠소" at 320 and 412; the errand and the bag left out at desktop). Try rewording the line in `scenarios/dawn/story.yaml`, or a check that compares who does what.

## 브람's "~소" lands on other endings

`qa_test/runs/ui-t13-1`, turn 4 at all three widths: "징수관은 우리 여관에 오지도 않았다소." The bio says he ends with "~소"; gemma4 glues it onto "-았다" despite the rule to write grammatical Korean. Try the bio's wording (an example sentence such as "왔소", "없소") or a grammar check.

## The ending text adds or bends facts

`qa_test/runs/ui-t14-1`: at 412, turn 27, the passage says "당신이 짚은 사람이 끌려가고" and gemma4 wrote "당신이 지목한 남자가" for 넬, a woman. At desktop, turn 11, the truth says the neck mark came from the cart rope; the ending calls it "범행의 흔적일 뿐". In `qa_test/runs/play-t15-1`, turn 9, it called 고드릭 "탐욕스러운 영주"; he is the village head. The ending is checked like a scene, so none was caught. Try naming the accused in the ending job, and a check against the truth text.

## A newcomer cannot tell what the notebook count means

`qa_test/runs/newbie-1` (a fresh agent playing the prologue from the shell): the top bar's count went 3 → 0 → 1 → 2 → 0 and stayed 0 at turn 11 although a heard line was new. It counts only unread seen things and items (game/07 2절); heard lines are left out because the chat already shows them. Decide whether to count every new line or to keep it.

## An answer can drop half of its line

`qa_test/runs/newbie-1`, turn 2: 최두식 said only "벨트는 6시까지 케이스에 있었다", while the notebook wrote the whole line with "강태오가 제일 수상하다" and added 강태오. Kanana's meaning check passed it. Same family as the first finding.
