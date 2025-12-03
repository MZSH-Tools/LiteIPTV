#!/bin/bash
# 快速验证脚本

cd "$(dirname "$0")"

echo "=== LiteIPTV Quick Test ==="
echo ""

# 设置快速测试模式
export QUICK_TEST=1

# 运行主程序
python3 main.py

echo ""
echo "=== Test Complete ==="
