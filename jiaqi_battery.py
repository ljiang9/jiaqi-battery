#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""假期电量模拟器 (jiaqi-battery)。

紧贴 2026-10-06 真实热梗「假期余额不足」：7 天长假，
每天安排 2 个活动，在耗电与回血之间走钢丝。
电量低于 20 进入低电量模式，归零则假期提前「关机」。

纯 Python 标准库，无第三方依赖。
"""

from __future__ import annotations

import argparse
import random
import sys

START_BATTERY = 100
LOW_BATTERY = 20
DAYS = 7
ACTS_PER_DAY = 2

# (名称, 电量变化, 快乐基准, 快乐抖动, 一句话描述)
# 快乐基准为 None 表示快乐完全随机（走亲戚：听天由命）
ACTIVITIES = [
    ("景区打卡", -18, 12, 4, "人山人海，但朋友圈九宫格赢了"),
    ("躺平刷手机", -6, 8, 3, "床是假期最后的堡垒"),
    ("高速堵车", -30, -8, 3, "在高速上看了一场免费日出"),
    ("走亲戚", -12, None, None, "快乐全看七大姑八大姨脸色"),
    ("加班回消息", -20, -10, 3, "假期余额 -20，老板余额 +1"),
    ("深夜烧烤", 10, 10, 3, "没有什么是一顿烧烤治愈不了的"),
]

# (名称, 电量变化, 快乐变化)
EVENTS = [
    ("老板深夜@全体成员", -10, -8),
    ("景区限流排队 3 小时", -8, -6),
    ("高速服务区充电排队", 5, -4),
]


class IllegalMove(ValueError):
    """非法活动编号。"""


def check_idx(idx):
    """校验活动编号，非法则抛 IllegalMove。"""
    if isinstance(idx, bool) or not isinstance(idx, int):
        raise IllegalMove(f"活动编号 {idx!r} 不合法，请输入 1-{len(ACTIVITIES)}")
    if not 0 <= idx < len(ACTIVITIES):
        raise IllegalMove(f"活动编号 {idx + 1} 不存在，请输入 1-{len(ACTIVITIES)}")
    return idx


def roll_activity(idx, rng):
    """结算一次活动，返回 (名称, 电量变化, 快乐值, 描述)。"""
    check_idx(idx)
    name, db, hb, jitter, desc = ACTIVITIES[idx]
    if hb is None:
        happy = rng.randint(-4, 14)  # 走亲戚：-4（催婚现场）~14（红包拿到手软）
    else:
        happy = hb + rng.randint(-jitter, jitter)
    return name, db, happy, desc


def clamp_battery(battery):
    """电量钳制在 [0, 100]。"""
    return max(0, min(START_BATTERY, battery))


def is_low(battery):
    """是否处于低电量模式：0 < 电量 < 20。"""
    return 0 < battery < LOW_BATTERY


def greedy_choice(battery, rng):
    """AI 贪心策略：在不关机的前提下最大化 快乐期望 + 电量变化*0.6。"""
    best_idx, best_score = 0, None
    for i, (_name, db, hb, _jitter, _desc) in enumerate(ACTIVITIES):
        est_happy = 5 if hb is None else hb  # 走亲戚快乐期望 = randint(-4,14) 的均值
        score = est_happy + db * 0.6 + rng.uniform(-2, 2)
        if battery + db <= 0:
            score -= 1000  # 关机警告：不到万不得已不选
        if best_score is None or score > best_score:
            best_idx, best_score = i, score
    return best_idx


def play_day(day, battery, happy_total, rng, choose, verbose=False):
    """模拟一天。返回 (battery, happy_total, early_off, low, day_happy, lines)。"""
    lines = []
    day_happy = 0
    early_off = False
    for slot in range(1, ACTS_PER_DAY + 1):
        idx = choose(battery, day, slot)
        name, db, happy, desc = roll_activity(idx, rng)
        battery = clamp_battery(battery + db)
        day_happy += happy
        lines.append(f"  活动{slot}：{name}（电量{db:+d}，快乐{happy:+d}）——{desc}")
        if battery <= 0:
            early_off = True
            lines.append("  ⚡ 电量归零！假期提前关机……")
            break
    if not early_off and rng.random() < 0.4:
        ev_name, ev_db, ev_happy = rng.choice(EVENTS)
        battery = clamp_battery(battery + ev_db)
        day_happy += ev_happy
        lines.append(f"  🎲 突发事件：{ev_name}（电量{ev_db:+d}，快乐{ev_happy:+d}）")
        if battery <= 0:
            early_off = True
            lines.append("  ⚡ 电量归零！假期提前关机……")
    low = False
    if not early_off and is_low(battery):
        low = True
        day_happy = int(day_happy * 0.5)
        lines.append("  ⚠️ 假期余额不足！低电量模式：今日快乐减半")
    happy_total = max(0, happy_total + day_happy)
    if verbose:
        print(f"—— 第 {day} 天 ——")
        for ln in lines:
            print(ln)
        print(f"  当日结算：电量 {battery}，快乐总值 {happy_total}"
              + ("（低电量模式）" if low else ""))
    return battery, happy_total, early_off, low, day_happy, lines


def ending(battery, happy, finished):
    """按剩余电量与快乐总值判定结局，返回 (标题, 评语)。"""
    if not finished:
        return ("假期提前关机",
                "电量归零，假期被迫提前结束——连充电宝都没救回来。")
    if happy >= 120 and battery < LOW_BATTERY:
        return ("假期刺客",
                "快乐拉满、电量见底：你把 7 天假期过成了极限运动，刺客本人。")
    if battery >= 60 and happy >= 60:
        return ("满血复活打工人",
                "电量健康、快乐在线，节后第一天你就是办公室最靓的仔。")
    if battery <= 10:
        return ("电量耗尽的空壳",
                "假期余额不足且无法充值，建议原地躺平等待下一个长假。")
    if happy >= 80:
        return ("快乐透支户",
                "快乐是真快乐，代价是节后要用三倍咖啡续命。")
    return ("平平无奇假期",
            "没翻车也没起飞，假期余额刚刚好——这已经赢了很多人。")


def play_game(rng, ai=True, verbose=False, choose=None):
    """完整模拟一局假期。返回结果 dict。"""
    battery, happy_total = START_BATTERY, 0
    finished = True
    low_days = 0
    if choose is None:
        if ai:
            choose = lambda b, d, s: greedy_choice(b, rng)
        else:
            raise IllegalMove("交互模式需要传入 choose 函数")
    for day in range(1, DAYS + 1):
        battery, happy_total, early_off, low, _dh, _lines = play_day(
            day, battery, happy_total, rng, choose, verbose)
        if low:
            low_days += 1
        if early_off:
            finished = False
            break
    title, comment = ending(battery, happy_total, finished)
    return {
        "battery": battery,
        "happy": happy_total,
        "finished": finished,
        "low_days": low_days,
        "title": title,
        "comment": comment,
    }


def run_auto(games, seed):
    """自动演示多局，返回每局结果列表（同 seed 结果可复现）。"""
    results = []
    for g in range(games):
        rng = random.Random(seed + g) if seed is not None else random.Random()
        results.append(play_game(rng, ai=True, verbose=False))
    return results


def interactive_choose_factory():
    def choose(battery, day, slot):
        while True:
            print(f"\n第 {day} 天 · 活动 {slot}/{ACTS_PER_DAY}（当前电量 {battery}）")
            for i, (name, db, _hb, _j, desc) in enumerate(ACTIVITIES, 1):
                tag = f"回血+{db}" if db > 0 else f"耗电{-db}"
                print(f"  {i}. {name} [{tag}] —— {desc}")
            raw = input("选一个（1-6，q 退出）：").strip()
            if raw.lower() == "q":
                print("假期提前结束，祝充电愉快。")
                raise SystemExit(0)
            try:
                return check_idx(int(raw) - 1)
            except (ValueError, IllegalMove):
                print("编号不对，再想想（1-6）。")
    return choose


def main(argv=None):
    parser = argparse.ArgumentParser(description="假期电量模拟器：7 天长假，100 格电，怎么花？")
    parser.add_argument("--auto", action="store_true", help="AI 自动演示，无需交互")
    parser.add_argument("--games", type=int, default=1, help="自动演示局数（默认 1）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--verbose", action="store_true", help="打印每日战报")
    args = parser.parse_args(argv)

    if args.auto:
        if args.games < 1:
            print("--games 至少为 1", file=sys.stderr)
            return 2
        results = []
        for g in range(args.games):
            rng = random.Random(args.seed + g) if args.seed is not None else random.Random()
            res = play_game(rng, ai=True, verbose=args.verbose)
            results.append(res)
            if args.verbose or args.games <= 5:
                print(f"第 {g + 1} 局：{res['title']}（剩余电量 {res['battery']}，"
                      f"快乐总值 {res['happy']}）——{res['comment']}")
        if args.games > 1:
            from collections import Counter
            dist = Counter(r["title"] for r in results)
            print(f"\n共 {args.games} 局，结局分布：")
            for title, cnt in dist.most_common():
                print(f"  {title}：{cnt} 局")
        return 0

    if not sys.stdin.isatty():
        print("需要交互式终端运行，或使用 --auto 自动演示。", file=sys.stderr)
        return 2
    rng = random.Random()
    res = play_game(rng, ai=False, verbose=True, choose=interactive_choose_factory())
    print(f"\n🏁 假期结束：{res['title']}")
    print(f"   剩余电量 {res['battery']}，快乐总值 {res['happy']}，低电量天数 {res['low_days']}")
    print(f"   {res['comment']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
