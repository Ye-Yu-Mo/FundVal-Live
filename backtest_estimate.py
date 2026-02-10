#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值算法回测脚本
评估自定义估值算法的历史准确率
"""
import sys
sys.path.insert(0, '/Users/jasxu/Documents/FundVal-Live/backend')

from app.services.estimate import estimate_with_weighted_ma, estimate_with_simple_ma
from app.services.fund import get_fund_history
import statistics


def backtest_algorithm(code: str, days: int = 60, test_days: int = 20):
    """
    回测估值算法

    Args:
        code: 基金代码
        days: 获取历史数据天数
        test_days: 回测天数（从最近的数据开始往前测试）

    Returns:
        回测结果字典
    """
    print(f"\n{'='*70}")
    print(f"回测基金: {code}")
    print(f"{'='*70}")

    # 获取历史数据
    history = get_fund_history(code, limit=days)
    if not history or len(history) < test_days + 10:
        print(f"❌ 历史数据不足（需要至少 {test_days + 10} 天，实际 {len(history) if history else 0} 天）")
        return None

    print(f"✓ 获取到 {len(history)} 天历史数据")
    print(f"  回测区间: {history[-test_days]['date']} ~ {history[-1]['date']}")

    results_wma = []  # 加权移动平均结果
    results_sma = []  # 简单移动平均结果

    # 从倒数第 test_days 天开始，逐日预测并对比实际值
    for i in range(test_days, 0, -1):
        # 使用前面的数据预测当天
        train_data = history[:-i]
        actual_nav = float(history[-i]["nav"])
        actual_date = history[-i]["date"]

        # 加权移动平均预测
        pred_wma = estimate_with_weighted_ma(train_data)
        if pred_wma:
            error_wma = abs(pred_wma["estimate"] - actual_nav)
            error_rate_wma = (error_wma / actual_nav) * 100
            results_wma.append({
                "date": actual_date,
                "actual": actual_nav,
                "predicted": pred_wma["estimate"],
                "error": error_wma,
                "error_rate": error_rate_wma,
                "predicted_change": pred_wma["est_rate"],
                "actual_change": ((actual_nav - float(train_data[-1]["nav"])) / float(train_data[-1]["nav"])) * 100
            })

        # 简单移动平均预测
        pred_sma = estimate_with_simple_ma(train_data)
        if pred_sma:
            error_sma = abs(pred_sma["estimate"] - actual_nav)
            error_rate_sma = (error_sma / actual_nav) * 100
            results_sma.append({
                "date": actual_date,
                "actual": actual_nav,
                "predicted": pred_sma["estimate"],
                "error": error_sma,
                "error_rate": error_rate_sma,
                "predicted_change": pred_sma["est_rate"],
                "actual_change": ((actual_nav - float(train_data[-1]["nav"])) / float(train_data[-1]["nav"])) * 100
            })

    # 统计结果
    if results_wma:
        print(f"\n【加权移动平均 - 回测结果】")
        print_backtest_stats(results_wma)

    if results_sma:
        print(f"\n【简单移动平均 - 回测结果】")
        print_backtest_stats(results_sma)

    # 对比
    if results_wma and results_sma:
        print(f"\n【算法对比】")
        avg_error_wma = statistics.mean([r["error_rate"] for r in results_wma])
        avg_error_sma = statistics.mean([r["error_rate"] for r in results_sma])
        winner = "加权移动平均" if avg_error_wma < avg_error_sma else "简单移动平均"
        print(f"  更优算法: {winner}")
        print(f"  误差差距: {abs(avg_error_wma - avg_error_sma):.3f}%")

    return {
        "code": code,
        "weighted_ma": results_wma,
        "simple_ma": results_sma
    }


def print_backtest_stats(results):
    """打印回测统计信息"""
    if not results:
        print("  无数据")
        return

    error_rates = [r["error_rate"] for r in results]
    errors = [r["error"] for r in results]

    # 方向准确率（预测涨跌方向是否正确）
    direction_correct = sum(
        1 for r in results
        if (r["predicted_change"] > 0 and r["actual_change"] > 0) or
           (r["predicted_change"] < 0 and r["actual_change"] < 0) or
           (r["predicted_change"] == 0 and r["actual_change"] == 0)
    )
    direction_accuracy = (direction_correct / len(results)) * 100

    print(f"  测试样本数: {len(results)}")
    print(f"  平均误差率: {statistics.mean(error_rates):.3f}%")
    print(f"  中位数误差率: {statistics.median(error_rates):.3f}%")
    print(f"  最大误差率: {max(error_rates):.3f}%")
    print(f"  最小误差率: {min(error_rates):.3f}%")
    print(f"  标准差: {statistics.stdev(error_rates) if len(error_rates) > 1 else 0:.3f}%")
    print(f"  方向准确率: {direction_accuracy:.1f}% ({direction_correct}/{len(results)})")

    # 误差分布
    within_05 = sum(1 for e in error_rates if e <= 0.5)
    within_10 = sum(1 for e in error_rates if e <= 1.0)
    within_20 = sum(1 for e in error_rates if e <= 2.0)

    print(f"\n  误差分布:")
    print(f"    ≤0.5%: {within_05}/{len(results)} ({within_05/len(results)*100:.1f}%)")
    print(f"    ≤1.0%: {within_10}/{len(results)} ({within_10/len(results)*100:.1f}%)")
    print(f"    ≤2.0%: {within_20}/{len(results)} ({within_20/len(results)*100:.1f}%)")

    # 显示最差的3个预测
    worst_cases = sorted(results, key=lambda x: x["error_rate"], reverse=True)[:3]
    print(f"\n  最差预测案例:")
    for i, case in enumerate(worst_cases, 1):
        print(f"    {i}. {case['date']}: 预测 {case['predicted']:.4f}, 实际 {case['actual']:.4f}, 误差 {case['error_rate']:.3f}%")


def batch_backtest(codes: list, days: int = 60, test_days: int = 20):
    """批量回测多个基金"""
    print(f"\n{'#'*70}")
    print(f"批量回测 - 共 {len(codes)} 只基金")
    print(f"回测参数: 历史数据 {days} 天, 测试 {test_days} 天")
    print(f"{'#'*70}")

    all_results = []
    for code in codes:
        result = backtest_algorithm(code, days, test_days)
        if result:
            all_results.append(result)

    # 汇总统计
    if all_results:
        print(f"\n{'='*70}")
        print(f"汇总统计 - {len(all_results)} 只基金")
        print(f"{'='*70}")

        all_wma_errors = []
        all_sma_errors = []

        for result in all_results:
            if result["weighted_ma"]:
                all_wma_errors.extend([r["error_rate"] for r in result["weighted_ma"]])
            if result["simple_ma"]:
                all_sma_errors.extend([r["error_rate"] for r in result["simple_ma"]])

        if all_wma_errors:
            print(f"\n【加权移动平均 - 总体表现】")
            print(f"  总样本数: {len(all_wma_errors)}")
            print(f"  平均误差率: {statistics.mean(all_wma_errors):.3f}%")
            print(f"  中位数误差率: {statistics.median(all_wma_errors):.3f}%")
            print(f"  标准差: {statistics.stdev(all_wma_errors):.3f}%")

            within_05 = sum(1 for e in all_wma_errors if e <= 0.5)
            within_10 = sum(1 for e in all_wma_errors if e <= 1.0)
            print(f"  误差 ≤0.5%: {within_05/len(all_wma_errors)*100:.1f}%")
            print(f"  误差 ≤1.0%: {within_10/len(all_wma_errors)*100:.1f}%")

        if all_sma_errors:
            print(f"\n【简单移动平均 - 总体表现】")
            print(f"  总样本数: {len(all_sma_errors)}")
            print(f"  平均误差率: {statistics.mean(all_sma_errors):.3f}%")
            print(f"  中位数误差率: {statistics.median(all_sma_errors):.3f}%")
            print(f"  标准差: {statistics.stdev(all_sma_errors):.3f}%")

            within_05 = sum(1 for e in all_sma_errors if e <= 0.5)
            within_10 = sum(1 for e in all_sma_errors if e <= 1.0)
            print(f"  误差 ≤0.5%: {within_05/len(all_sma_errors)*100:.1f}%")
            print(f"  误差 ≤1.0%: {within_10/len(all_sma_errors)*100:.1f}%")


if __name__ == "__main__":
    # 测试多种类型的基金
    test_codes = [
        "005827",  # 易方达蓝筹精选（主动管理）
        "110003",  # 易方达上证50（指数基金）
        "000001",  # 华夏成长（混合型）
        "161725",  # 招商中证白酒（行业指数）
        "163406",  # 兴全合润（混合型）
    ]

    # 批量回测
    batch_backtest(test_codes, days=60, test_days=20)
