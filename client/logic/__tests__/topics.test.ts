import { splitTopics } from '../topics';

test('topic names in what a person says are cut out to be underlined', () => {
  expect(splitTopics('봉식아, 벨트 얘기라면 나도 아는 게 있다.', ['벨트', '그 시각'])).toEqual([
    { text: '봉식아, ', topic: false }, { text: '벨트', topic: true }, { text: ' 얘기라면 나도 아는 게 있다.', topic: false },
  ]);
  expect(splitTopics('새벽 종이 울렸습니다.', ['새벽', '새벽 종'])).toEqual([
    { text: '새벽 종', topic: true }, { text: '이 울렸습니다.', topic: false },
  ]);
  expect(splitTopics('아무 말', [])).toEqual([{ text: '아무 말', topic: false }]);
});
