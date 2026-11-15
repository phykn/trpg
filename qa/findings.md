# Open problems

Each with its evidence (`qa_test/runs/<run>`, turn numbers).

## The text check misses a changed meaning

`qa_test/runs/text-dawn-3/results.json`, case `말 브람.징수관.깨진 뒤`: gemma4 wrote "그건 모르겠소. 나는 이제 장부를 맞추러 촌장 댁에 가봐야 하니, 이 가방 좀 맡아주시오." It drops the bribe and turns the collector's errand into 브람's, yet Kanana's meaning check gave 0.84. The line's "그는" is easy to misread. The notebook keeps the true line, so the deduction is not lost, but the spoken answer misleads. Try rewording the line in `scenarios/dawn/story.yaml`, or a check that compares who does what.

