#!/usr/bin/env python3
"""
Decision Helper for Language Choice
Asks key questions to help decide whether to refactor.
"""

import sys

def ask_question(question, options):
    """Ask a question with multiple choice options."""
    print(f"\n{question}")
    for i, (key, text) in enumerate(options.items(), 1):
        print(f"  {i}. {text}")
    
    while True:
        try:
            choice = input(f"\nEnter choice (1-{len(options)}): ").strip()
            if not choice:
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return list(options.keys())[idx]
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(options)}")

def main():
    print("🤔 Language Refactor Decision Helper")
    print("=" * 60)
    print("Answer these questions to determine if you should refactor.\n")
    
    answers = {}
    
    # Question 1: Performance requirements
    answers['performance'] = ask_question(
        "1. What's your target cycle time?",
        {
            "a": "< 1 second (ultra-low latency)",
            "b": "1-5 seconds (competitive trading)",
            "c": "5-30 seconds (standard trading)",
            "d": "> 30 seconds (research/analysis)",
        }
    )
    
    # Question 2: Current bottlenecks
    answers['bottleneck'] = ask_question(
        "2. What's your main bottleneck?",
        {
            "a": "HTTP API calls (DexScreener, GoPlus, etc.)",
            "b": "Web3/RPC calls (Ethereum node)",
            "c": "CPU processing (calculations, ML)",
            "d": "Memory usage (large datasets)",
        }
    )
    
    # Question 3: Team expertise
    answers['team'] = ask_question(
        "3. What's your team's expertise?",
        {
            "a": "Mostly Python experts",
            "b": "Mix of Python and Go/Rust",
            "c": "Mostly Go/Rust experts",
            "d": "Mostly JavaScript/TypeScript",
        }
    )
    
    # Question 4: Time constraints
    answers['time'] = ask_question(
        "4. What's your time constraint?",
        {
            "a": "Need improvements in days",
            "b": "Weeks to a month is OK",
            "c": "Months is acceptable",
            "d": "No specific deadline",
        }
    )
    
    # Question 5: Codebase size
    answers['codebase'] = ask_question(
        "5. How much code would need rewriting?",
        {
            "a": "Small (< 10k lines)",
            "b": "Medium (10k-100k lines)",
            "c": "Large (100k-1M lines)",
            "d": "Very large (> 1M lines) - like yours",
        }
    )
    
    # Analyze answers
    print("\n" + "=" * 60)
    print("📊 ANALYSIS & RECOMMENDATION")
    print("=" * 60)
    
    # Scoring system
    python_score = 0
    go_score = 0
    rust_score = 0
    ts_score = 0
    
    # Performance requirements
    if answers['performance'] == 'a':  # < 1 second
        go_score += 3
        rust_score += 3
        python_score -= 1
    elif answers['performance'] == 'b':  # 1-5 seconds
        python_score += 2
        go_score += 1
    else:  # 5+ seconds
        python_score += 3
    
    # Bottleneck analysis
    if answers['bottleneck'] in ['a', 'b']:  # I/O bound
        python_score += 2  # Async Python can handle
        go_score += 1
    elif answers['bottleneck'] == 'c':  # CPU bound
        go_score += 2
        rust_score += 3
        python_score -= 1
    elif answers['bottleneck'] == 'd':  # Memory bound
        rust_score += 2
        go_score += 1
    
    # Team expertise
    if answers['team'] == 'a':  # Python experts
        python_score += 3
    elif answers['team'] == 'b':  # Mixed
        python_score += 1
        go_score += 1
    elif answers['team'] == 'c':  # Go/Rust experts
        go_score += 3
        rust_score += 2
    elif answers['team'] == 'd':  # JS/TS experts
        ts_score += 3
    
    # Time constraints
    if answers['time'] == 'a':  # Days
        python_score += 3
    elif answers['time'] == 'b':  # Weeks
        python_score += 2
        go_score += 1
    elif answers['time'] == 'c':  # Months
        go_score += 2
        rust_score += 1
    else:  # No deadline
        rust_score += 2
    
    # Codebase size
    if answers['codebase'] in ['c', 'd']:  # Large/Very large
        python_score += 3  # Rewrite cost too high
        go_score -= 1
        rust_score -= 2
    elif answers['codebase'] == 'b':  # Medium
        python_score += 1
    else:  # Small
        go_score += 1
        rust_score += 1
    
    # Calculate recommendations
    scores = {
        'Python': python_score,
        'Go': go_score,
        'Rust': rust_score,
        'TypeScript': ts_score,
    }
    
    print("\n📈 Recommendation Scores:")
    for lang, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  {lang:12} {score:3} {'⭐' * max(0, min(5, score))}")
    
    # Determine recommendation
    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]
    
    print(f"\n🎯 Primary Recommendation: {best_lang}")
    
    # Provide reasoning
    print("\n📝 Reasoning:")
    
    if best_lang == 'Python':
        print("  • Your codebase is large (>1M lines)")
        print("  • Rewrite cost would be prohibitive")
        print("  • Python can be optimized for your needs")
        print("  • Team expertise and development speed are priorities")
        
        print("\n🚀 Action Plan:")
        print("  1. Run benchmark_current.py to measure performance")
        print("  2. Implement async/await for I/O operations")
        print("  3. Add connection pooling and caching")
        print("  4. Profile to find exact bottlenecks")
        print("  5. Re-evaluate in 4 weeks")
        
    elif best_lang == 'Go':
        print("  • You need better performance than Python can provide")
        print("  • Go offers excellent concurrency for I/O operations")
        print("  • Good balance of performance and development speed")
        
        print("\n🚀 Action Plan:")
        print("  1. Start with hybrid approach: Python + Go")
        print("  2. Rewrite performance-critical components in Go")
        print("  3. Use gRPC for Python-Go communication")
        print("  4. Gradually migrate more components")
        
    elif best_lang == 'Rust':
        print("  • You need maximum performance and memory safety")
        print("  • CPU-bound operations are your bottleneck")
        print("  • You have time for a longer rewrite")
        
        print("\n🚀 Action Plan:")
        print("  1. Start with a small prototype in Rust")
        print("  2. Rewrite one component at a time")
        print("  3. Expect significant learning curve")
        print("  4. Consider Rust only for performance-critical parts")
        
    elif best_lang == 'TypeScript':
        print("  • Your team knows JavaScript/TypeScript")
        print("  • You're using MCP (JavaScript-based)")
        print("  • Good for I/O-heavy applications")
        
        print("\n🚀 Action Plan:")
        print("  1. Start with TypeScript for new components")
        print("  2. Use Deno/Bun for better performance")
        print("  3. Consider gradual migration from Python")
    
    # Special note for your specific case
    print("\n" + "=" * 60)
    print("⚠️  SPECIAL NOTE FOR YOUR CASE")
    print("=" * 60)
    print("You have 1.2M lines of Python code. This changes everything:")
    print("• Full rewrite: ~6-12 developer-years")
    print("• Cost: $1-2M+ in developer time")
    print("• Risk: Very high (could fail or introduce bugs)")
    print("• Opportunity cost: Can't ship new features during rewrite")
    print("\n✅ Recommendation: Optimize Python first, measure results.")
    
    print("\n" + "=" * 60)
    print("📚 Next Steps:")
    print("1. Read: LANGUAGE_DECISION_MATRIX.md")
    print("2. Read: OPTIMIZATION_PLAN.md")
    print("3. Run: python benchmark_current.py")
    print("4. Start with Phase 1 optimizations")
    print("=" * 60)

if __name__ == "__main__":
    main()