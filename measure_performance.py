#!/usr/bin/env python3
"""Performance baseline measurement script."""

import time
import sys
from statistics import mean, stdev

def measure_import_time(module_name, import_statement, iterations=10):
    """Measure the time to import a module."""
    times = []
    
    for i in range(iterations):
        # Clear module from cache
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Clear related modules
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('quantalogic')]
        for mod in modules_to_clear:
            del sys.modules[mod]
        
        start_time = time.perf_counter()
        try:
            exec(import_statement)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)  # Convert to milliseconds
        except Exception as e:
            print(f"Import failed: {e}")
            times.append(float('inf'))
    
    # Filter out failed imports
    valid_times = [t for t in times if t != float('inf')]
    
    if not valid_times:
        return None, None, None
    
    return mean(valid_times), stdev(valid_times) if len(valid_times) > 1 else 0, valid_times

def measure_cli_startup_time(iterations=5):
    """Measure CLI startup time."""
    import subprocess
    times = []
    
    for i in range(iterations):
        start_time = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, "-c", "from quantalogic.main import cli; print('CLI loaded')"],
                capture_output=True,
                text=True,
                timeout=30
            )
            end_time = time.perf_counter()
            if result.returncode == 0:
                times.append((end_time - start_time) * 1000)
            else:
                print(f"CLI test failed: {result.stderr}")
                times.append(float('inf'))
        except Exception as e:
            print(f"CLI test error: {e}")
            times.append(float('inf'))
    
    valid_times = [t for t in times if t != float('inf')]
    if not valid_times:
        return None, None, None
    
    return mean(valid_times), stdev(valid_times) if len(valid_times) > 1 else 0, valid_times

def main():
    print("📊 QuantaLogic Performance Baseline Measurement")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        ("Agent Import", "quantalogic", "from quantalogic import Agent"),
        ("Tools Import", "quantalogic.tools", "from quantalogic.tools import Tool"),
        ("Flow Import", "quantalogic.flow", "from quantalogic.flow import Workflow"),
        ("Full Import", "quantalogic", "from quantalogic import Agent, EventEmitter, AgentMemory"),
    ]
    
    results = {}
    
    print("🔍 Testing import performance...")
    for test_name, module_name, import_stmt in test_cases:
        print(f"Testing {test_name}...")
        avg_time, std_time, all_times = measure_import_time(module_name, import_stmt)
        
        if avg_time is not None:
            results[test_name] = {
                'avg_ms': avg_time,
                'std_ms': std_time,
                'all_times': all_times
            }
            print(f"  ✅ {avg_time:.2f}ms ± {std_time:.2f}ms")
        else:
            results[test_name] = {'error': 'Failed to import'}
            print(f"  ❌ Failed")
    
    print("\n🚀 Testing CLI startup performance...")
    cli_avg, cli_std, cli_times = measure_cli_startup_time()
    if cli_avg is not None:
        results['CLI Startup'] = {
            'avg_ms': cli_avg,
            'std_ms': cli_std,
            'all_times': cli_times
        }
        print(f"  ✅ {cli_avg:.2f}ms ± {cli_std:.2f}ms")
    else:
        results['CLI Startup'] = {'error': 'Failed to measure'}
        print(f"  ❌ Failed")
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    with open(f"performance_baseline_{timestamp}.txt", "w") as f:
        f.write("QuantaLogic Performance Baseline\n")
        f.write("=" * 35 + "\n")
        f.write(f"Measured at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for test_name, result in results.items():
            f.write(f"{test_name}:\n")
            if 'error' in result:
                f.write(f"  Error: {result['error']}\n")
            else:
                f.write(f"  Average: {result['avg_ms']:.2f}ms\n")
                f.write(f"  Std Dev: {result['std_ms']:.2f}ms\n")
                f.write(f"  All times: {result['all_times']}\n")
            f.write("\n")
    
    print(f"\n📄 Results saved to: performance_baseline_{timestamp}.txt")
    print("\n📊 Summary:")
    print("-" * 30)
    for test_name, result in results.items():
        if 'error' not in result:
            print(f"{test_name:20} {result['avg_ms']:>8.2f}ms")
    
    return results

if __name__ == "__main__":
    main()
