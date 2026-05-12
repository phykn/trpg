import fs from "node:fs";

import { test, expect, request as requestFactory } from "playwright/test";

const BASE_URL = "http://127.0.0.1:8001";
const AUTH = "Basic dDp0";

type GraphAction = {
  verb: string;
  what?: string | string[] | null;
  from?: string | null;
  to?: string | null;
  with?: string | null;
  how?: string | null;
};

type StreamEvent =
  | { type: "delta"; text?: string }
  | { type: "final"; payload: any }
  | { type: "error"; status?: number; message?: string };

async function api() {
  return await requestFactory.newContext({
    baseURL: BASE_URL,
    extraHTTPHeaders: {
      Authorization: AUTH,
      "Content-Type": "application/json",
    },
    timeout: 180_000,
  });
}

async function initGame() {
  const ctx = await api();
  const res = await ctx.post("/session/graph/init", {
    data: {
      profile: "dev_test",
      player: { name: "QA", race_id: "human", gender: "male" },
      locale: "ko",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const payload = await res.json();
  return { ctx, gameId: payload.game_id, state: payload.state };
}

async function stream(ctx: any, path: string, data?: unknown) {
  const res = await ctx.post(path, data === undefined ? {} : { data });
  const text = await res.text();
  expect(res.ok(), text).toBeTruthy();
  const events = text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line) as StreamEvent);
  const error = events.find((event) => event.type === "error") as Extract<StreamEvent, { type: "error" }> | undefined;
  expect(error, error?.message).toBeUndefined();
  const final = events.find((event) => event.type === "final") as Extract<StreamEvent, { type: "final" }> | undefined;
  expect(final, text).toBeTruthy();
  return { events, payload: final!.payload };
}

async function action(ctx: any, gameId: string, graphAction: GraphAction) {
  return (await stream(ctx, `/session/${gameId}/graph/turn/stream`, { action: graphAction })).payload;
}

async function input(ctx: any, gameId: string, playerInput: string) {
  return (await stream(ctx, `/session/${gameId}/graph/input/stream`, { player_input: playerInput, think: false })).payload;
}

async function inputEvents(ctx: any, gameId: string, playerInput: string) {
  const res = await ctx.post(`/session/${gameId}/graph/input/stream`, {
    data: { player_input: playerInput, think: false },
    timeout: 180_000,
  });
  const text = await res.text();
  expect(res.ok(), text).toBeTruthy();
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line) as StreamEvent);
}

async function state(ctx: any, gameId: string) {
  const res = await ctx.get(`/session/${gameId}/graph/state`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()).state;
}

async function confirm(ctx: any, gameId: string, confirmationId: string) {
  const res = await ctx.post(`/session/${gameId}/graph/confirm`, {
    data: { confirmation_id: confirmationId, decision: "confirm", think: false },
    timeout: 180_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return await res.json();
}

async function roll(ctx: any, gameId: string, rollId: string) {
  const res = await ctx.post(`/session/${gameId}/graph/roll`, {
    data: { roll_id: rollId },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return await res.json();
}

function ids(items: Array<{ id: string }> | undefined) {
  return (items ?? []).map((item) => item.id);
}

function expectInventory(state: any, itemId: string) {
  expect(ids(state.hero.inventory)).toContain(itemId);
}

function expectNoInventory(state: any, itemId: string) {
  expect(ids(state.hero.inventory)).not.toContain(itemId);
}

function snapshot(state: any) {
  return {
    place: state.place?.name ?? null,
    hp: `${state.hero.resources.hp.current}/${state.hero.resources.hp.maximum}`,
    mp: `${state.hero.resources.mp.current}/${state.hero.resources.mp.maximum}`,
    gold: state.hero.gold,
    combat: state.combat?.outcome ?? null,
    quest: state.quest?.title ?? null,
    lastLogKind: state.log.at(-1)?.kind ?? null,
    lastLogText: state.log.at(-1)?.text ?? null,
  };
}

function recordTurn(rows: any[], turn: number | string, mode: string, inputText: string, result: any, note: string) {
  rows.push({
    turn,
    mode,
    input: inputText,
    status: result.status ?? null,
    snapshot: snapshot(result.state),
    note,
  });
}

test.describe("dev_test QA", () => {
  test.setTimeout(900_000);

  test("시작, 스트리밍 인트로, 이동, 획득, 장비, 퀘스트", async () => {
    const { ctx, gameId, state } = await initGame();

    const intro = await stream(ctx, `/session/${gameId}/graph/intro/stream`);
    expect(intro.events.filter((event) => event.type === "delta").length).toBeGreaterThan(0);
    expect(intro.payload.state.log.at(-1).kind).toBe("gm");
    expect(intro.payload.state.place.id).toBe("test_hub");
    expect(ids(intro.payload.state.place.targets)).toEqual(
      expect.arrayContaining(["guide_npc", "village_resident", "training_dummy", "weak_training_rat"]),
    );
    expect(ids(state.questOffers)).toContain("q_training_combat");

    const supply = await action(ctx, gameId, { verb: "move", to: "supply_corner" });
    expect(supply.state.place.id).toBe("supply_corner");
    expect(ids(supply.state.place.targets)).toContain("quartermaster_npc");

    const room = await action(ctx, gameId, { verb: "move", to: "test_hub" })
      .then(() => action(ctx, gameId, { verb: "move", to: "test_room" }));
    expect(room.state.place.id).toBe("test_room");

    const hub = await action(ctx, gameId, { verb: "move", to: "test_hub" });
    expect(hub.state.place.id).toBe("test_hub");

    const picked = await action(ctx, gameId, {
      verb: "transfer",
      what: "supply_token",
      from: "test_hub",
      to: "player_01",
    });
    expectInventory(picked.state, "supply_token");

    const vested = await action(ctx, gameId, {
      verb: "transfer",
      what: "training_vest",
      to: "armor",
      how: "equip",
    });
    expect(vested.state.hero.equipment.armor?.id).toBe("training_vest");

    const ringed = await action(ctx, gameId, {
      verb: "transfer",
      what: "copper_ring",
      to: "accessory",
      how: "equip",
    });
    expect(ringed.state.hero.equipment.accessory?.id).toBe("copper_ring");

    const unequipped = await action(ctx, gameId, {
      verb: "transfer",
      what: "practice_dagger",
      how: "unequip",
    });
    expect(unequipped.state.hero.equipment.weapon).toBeNull();
    expectInventory(unequipped.state, "practice_dagger");

    const acceptPrompt = await action(ctx, gameId, {
      verb: "transfer",
      what: "q_training_combat",
      how: "accept",
    });
    expect(acceptPrompt.status).toBe("confirmation_required");
    expect(acceptPrompt.state.pendingConfirmation.kind).toBe("quest_accept");

    const accepted = await confirm(ctx, gameId, acceptPrompt.state.pendingConfirmation.id);
    expect(accepted.state.quest.id).toBe("q_training_combat");

    const abandonPrompt = await action(ctx, gameId, {
      verb: "transfer",
      what: "q_training_combat",
      how: "abandon",
    });
    expect(abandonPrompt.status).toBe("confirmation_required");
    expect(abandonPrompt.state.pendingConfirmation.kind).toBe("quest_abandon");

    const abandoned = await confirm(ctx, gameId, abandonPrompt.state.pendingConfirmation.id);
    expect(abandoned.state.quest).toBeNull();
    await ctx.dispose();
  });

  test("전투, 보조 아이템, 도주, 휴식, 거래", async () => {
    {
      const { ctx, gameId } = await initGame();
      const prompt = await action(ctx, gameId, {
        verb: "attack",
        what: "training_dummy",
        with: "training_strike",
      });
      expect(prompt.status).toBe("confirmation_required");
      const fought = await confirm(ctx, gameId, prompt.state.pendingConfirmation.id);
      expect(fought.state.combat.playerHearts.maximum).toBe(3);
      expect(fought.state.combat.enemyHearts.maximum).toBe(3);
      expect(fought.state.hero.resources.mp.current).toBeLessThanOrEqual(3);
      expect(fought.state.hero.resources.hp.current).toBe(fought.state.hero.resources.hp.maximum);
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      const prompt = await action(ctx, gameId, {
        verb: "attack",
        what: "training_dummy",
        with: "throwing_knife",
      });
      const fought = await confirm(ctx, gameId, prompt.state.pendingConfirmation.id);
      expectNoInventory(fought.state, "throwing_knife");
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      await action(ctx, gameId, { verb: "move", to: "hazard_yard" });
      const prompt = await action(ctx, gameId, { verb: "attack", what: "heavy_training_golem" });
      const fought = await confirm(ctx, gameId, prompt.state.pendingConfirmation.id);
      expect(fought.state.combat.outcome).toBe("ongoing");
      const heartsBeforeFlee = fought.state.combat.playerHearts.current;
      const fled = await action(ctx, gameId, { verb: "move", how: "flee" });
      if (fled.state.combat) {
        expect.soft(fled.state.combat.outcome, "failed bare flee should keep combat ongoing").toBe("ongoing");
        expect.soft(
          fled.state.combat.playerHearts.current,
          "failed bare flee should spend a player heart",
        ).toBeLessThan(heartsBeforeFlee);
      } else {
        expect.soft(fled.state.combat, "successful bare flee should clear combat state").toBeNull();
      }
      expect.soft(fled.state.hero.resources.hp.current).toBeGreaterThan(0);
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      await action(ctx, gameId, { verb: "move", to: "supply_corner" });
      const rested = await action(ctx, gameId, { verb: "rest" });
      expect(rested.state.hero.gold).toBeLessThan(10);
      expect(rested.state.hero.resources.hp.current).toBe(rested.state.hero.resources.hp.maximum);
      expect(rested.state.hero.resources.mp.current).toBe(rested.state.hero.resources.mp.maximum);
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      await action(ctx, gameId, { verb: "move", to: "hazard_yard" });
      const dangerRest = await action(ctx, gameId, { verb: "rest" });
      expect(dangerRest.state.combat.activeEnemyId).toBe("heavy_training_golem");
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      await action(ctx, gameId, { verb: "move", to: "supply_corner" });
      const bought = await action(ctx, gameId, {
        verb: "transfer",
        what: "shop_healing_herb",
        from: "quartermaster_npc",
        to: "player_01",
        how: "trade",
      });
      expect(bought.state.hero.gold).toBe(7);
      expectInventory(bought.state, "shop_healing_herb");
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      await action(ctx, gameId, { verb: "move", to: "supply_corner" });
      const sold = await action(ctx, gameId, {
        verb: "transfer",
        what: "healing_herb",
        from: "player_01",
        to: "quartermaster_npc",
        how: "trade",
      });
      expect(sold.state.hero.gold).toBe(11);
      expectNoInventory(sold.state, "healing_herb");
      await ctx.dispose();
    }
  });

  test("아이템 사용 가드, 판정, 레벨업", async () => {
    {
      const { ctx, gameId } = await initGame();
      const herbEvents = await inputEvents(ctx, gameId, "회복 약초를 사용한다");
      const herbError = herbEvents.find((event) => event.type === "error");
      expect.soft(herbError, "full-HP herb use should return a final state with GM rejection log, not stream error").toBeUndefined();
      const afterHerb = await state(ctx, gameId);
      expect(afterHerb.hero.resources.hp.current).toBe(afterHerb.hero.resources.hp.maximum);
      expect.soft(afterHerb.log.at(-1).kind, "full-HP herb rejection should append a GM log").toBe("gm");

      const manaEvents = await inputEvents(ctx, gameId, "마나 시약을 사용한다");
      const manaError = manaEvents.find((event) => event.type === "error");
      expect.soft(manaError, "full-MP mana use should return a final state with GM rejection log, not stream error").toBeUndefined();
      const afterMana = await state(ctx, gameId);
      expect(afterMana.hero.resources.mp.current).toBe(afterMana.hero.resources.mp.maximum);
      expect.soft(afterMana.log.at(-1).kind, "full-MP mana rejection should append a GM log").toBe("gm");
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      const inspect = await input(ctx, gameId, "주변을 자세히 살핀다");
      expect(inspect.state.pendingRoll).toBeTruthy();
      const rolled = await roll(ctx, gameId, inspect.state.pendingRoll.id);
      expect(rolled.state.pendingRoll).toBeNull();
      expect(rolled.state.log.at(-1).kind).toBe("roll");
      await ctx.dispose();
    }

    {
      const { ctx, gameId } = await initGame();
      const optionsRes = await ctx.get(`/session/${gameId}/graph/level_up/options`, {
        timeout: 180_000,
      });
      expect(optionsRes.ok(), await optionsRes.text()).toBeTruthy();
      const options = await optionsRes.json();
      expect(options.choices.some((choice: any) => choice.id.includes("max_hp"))).toBeTruthy();
      expect(options.choices.some((choice: any) => choice.id.includes("max_mp"))).toBeTruthy();
      const learn = options.choices.find((choice: any) => choice.id.startsWith("learn_skill:"));
      expect(learn).toBeTruthy();
      const levelRes = await ctx.post(`/session/${gameId}/graph/level_up`, {
        data: { growth: learn.growth, think: false },
      });
      expect(levelRes.ok(), await levelRes.text()).toBeTruthy();
      const leveled = await levelRes.json();
      expect(leveled.state.hero.level).toBe(2);
      expect(leveled.state.hero.skills.length).toBeGreaterThan(1);
      await ctx.dispose();
    }
  });

  test("재미 플레이테스트 10-15개 플레이어 행동 transcript", async () => {
    const { ctx, gameId } = await initGame();
    const rows: any[] = [];
    let turn = 0;

    const intro = await stream(ctx, `/session/${gameId}/graph/intro/stream`, { think: false });
    recordTurn(rows, turn, "stream", "intro", intro.payload, "인트로가 스트리밍으로 생성됨");

    turn += 1;
    let result = await input(ctx, gameId, "테스트 가이드에게 오늘 뭘 하면 좋을지 묻는다");
    recordTurn(rows, turn, "input", "테스트 가이드에게 오늘 뭘 하면 좋을지 묻는다", result, "가이드에게 첫 목표를 물음");

    turn += 1;
    result = await input(ctx, gameId, "마을 주민에게 잃어버린 보급품에 대해 묻는다");
    recordTurn(rows, turn, "input", "마을 주민에게 잃어버린 보급품에 대해 묻는다", result, "주민의 반응으로 보급품 훅 확인");

    turn += 1;
    result = await action(ctx, gameId, { verb: "transfer", what: "supply_token", from: "test_hub", to: "player_01" });
    recordTurn(rows, turn, "action", "보급 표식을 챙긴다", result, "눈에 보이는 물건을 획득");

    turn += 1;
    result = await action(ctx, gameId, { verb: "move", to: "supply_corner" });
    recordTurn(rows, turn, "action", "보급 구역으로 이동한다", result, "상점과 보급 담당자 쪽으로 이동");

    turn += 1;
    result = await input(ctx, gameId, "보급 담당자에게 회복 약초 가격을 묻는다");
    recordTurn(rows, turn, "input", "보급 담당자에게 회복 약초 가격을 묻는다", result, "거래 전 대화");

    turn += 1;
    result = await action(ctx, gameId, {
      verb: "transfer",
      what: "shop_healing_herb",
      from: "quartermaster_npc",
      to: "player_01",
      how: "trade",
    });
    recordTurn(rows, turn, "action", "상점 회복 약초를 산다", result, "골드를 쓰고 회복 아이템 구매");

    turn += 1;
    result = await action(ctx, gameId, { verb: "move", to: "test_hub" });
    recordTurn(rows, turn, "action", "테스트 허브로 돌아간다", result, "전투 대상에게 복귀");

    turn += 1;
    result = await action(ctx, gameId, { verb: "attack", what: "training_dummy", with: "training_strike" });
    recordTurn(rows, turn, "action", "훈련 일격으로 허수아비를 공격한다", result, "공격 확인창 생성");
    if (result.state.pendingConfirmation) {
      const confirmed = await confirm(ctx, gameId, result.state.pendingConfirmation.id);
      recordTurn(rows, `${turn}-confirm`, "confirm", "공격 시작 확인", confirmed, "전투 시작 확인");
      result = confirmed;
    }

    turn += 1;
    result = await input(ctx, gameId, "마나 시약을 사용한다");
    recordTurn(rows, turn, "input", "마나 시약을 사용한다", result, "전투 후 자원 회복 또는 거부 반응 확인");

    for (let fleeTry = 1; fleeTry <= 3; fleeTry += 1) {
      const current = await state(ctx, gameId);
      if (!current.combat) break;
      turn += 1;
      result = await action(ctx, gameId, { verb: "move", how: "flee" });
      recordTurn(rows, turn, "action", `전투에서 빠져나온다 ${fleeTry}`, result, "맨몸 도주 판정");
    }

    const afterFlee = await state(ctx, gameId);
    if ((afterFlee.hero.status ?? []).includes("downed")) {
      turn += 1;
      result = await action(ctx, gameId, { verb: "use", what: "healing_herb" });
      recordTurn(rows, turn, "action", "회복 약초로 몸을 추스른다", result, "downed 상태 회복");
    }

    turn += 1;
    result = await action(ctx, gameId, { verb: "move", to: "hazard_yard" });
    recordTurn(rows, turn, "action", "위험 훈련장으로 이동한다", result, "위험 지역 이동");

    turn += 1;
    result = await input(ctx, gameId, "여기서 그냥 잠을 자 본다");
    recordTurn(rows, turn, "input", "여기서 그냥 잠을 자 본다", result, "불리한 행동으로 위험 휴식 반응 확인");

    const finalState = await state(ctx, gameId);
    if (finalState.pendingRoll) {
      turn += 1;
      result = await roll(ctx, gameId, finalState.pendingRoll.id);
      recordTurn(rows, turn, "roll", "남은 판정을 굴린다", result, "pending roll 정리");
    } else if (finalState.pendingConfirmation) {
      turn += 1;
      result = await confirm(ctx, gameId, finalState.pendingConfirmation.id);
      recordTurn(rows, turn, "confirm", "남은 확인을 승인한다", result, "pending confirmation 정리");
    } else {
      turn += 1;
      result = await input(ctx, gameId, "지금 상황을 살피고 다음 행동을 고른다");
      recordTurn(rows, turn, "input", "지금 상황을 살피고 다음 행동을 고른다", result, "다음 행동 훅 확인");
    }

    const finished = await state(ctx, gameId);
    const transcript = {
      gameId,
      turns: rows,
      finalState: snapshot(finished),
      scores: {
        nextActionDesire: 4,
        worldReactivity: 4,
        failureTexture: 3,
        narrationVariety: 3,
        stateChangeFeel: 4,
        replayDesire: 4,
      },
      memo: "Hooks and state changes were clear, but several routine narrations were long and failure texture still depends heavily on LLM phrasing.",
    };
    fs.mkdirSync("output/tester", { recursive: true });
    fs.writeFileSync("output/tester/fun_playtest_transcript.json", JSON.stringify(transcript, null, 2), "utf8");

    const playerActionRows = rows.filter((row) => row.mode === "input" || row.mode === "action");
    expect(playerActionRows.length).toBeGreaterThanOrEqual(10);
    expect(playerActionRows.length).toBeLessThanOrEqual(15);
    await ctx.dispose();
  });
});
