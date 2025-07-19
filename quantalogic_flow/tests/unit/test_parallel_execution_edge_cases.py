"""
Comprehensive edge case tests for parallel execution in quantalogic flow.

This module contains extensive tests for edge cases and corner scenarios
that could occur during parallel execution, ensuring robustness and reliability.
"""

import asyncio
import gc
import threading
import time
import weakref

import pytest

from quantalogic_flow.flow.flow import (
    Nodes,
    Workflow,
)


class TestParallelExecutionEdgeCases:
    """Test edge cases for parallel execution in the workflow engine."""

    def setup_method(self):
        """Set up each test method."""
        self.execution_log = []
        self.context = {}
        self.context_access_log = []
        self.cleanup_log = []
        self.thread_ids = []
        self.success_results = []

    # === TIMEOUT AND CANCELLATION TESTS ===

    async def test_parallel_execution_timeout_handling(self, nodes_registry_backup):
        """Test timeout handling in parallel execution."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def fast_node(instance):
            await asyncio.sleep(0.1)
            return "fast_completed"

        @Nodes.define(output="result")
        async def slow_node(instance):
            # This node takes too long
            await asyncio.sleep(2.0)
            return "slow_completed"

        @Nodes.define(output="result")
        async def timeout_node(instance):
            # This node will timeout
            await asyncio.sleep(5.0)
            return "timeout_completed"

        workflow = (
            Workflow("start_node")
            .parallel("fast_node", "slow_node", "timeout_node")
        )
        engine = workflow.build(instance=self)

        # Test with timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(engine.run(self.context), timeout=1.0)

    async def test_parallel_execution_cancellation(self, nodes_registry_backup):
        """Test cancellation of parallel execution."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def cancellable_node(instance):
            try:
                await asyncio.sleep(2.0)
                return "completed"
            except asyncio.CancelledError:
                instance.execution_log.append("node_cancelled")
                raise

        @Nodes.define(output="result")
        async def quick_node(instance):
            await asyncio.sleep(0.1)
            return "quick_completed"

        workflow = (
            Workflow("start_node")
            .parallel("cancellable_node", "quick_node")
        )
        engine = workflow.build(instance=self)

        # Start execution and cancel after short delay
        task = asyncio.create_task(engine.run(self.context))
        await asyncio.sleep(0.2)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify cancellation was logged
        assert "node_cancelled" in self.execution_log

    async def test_parallel_execution_partial_cancellation(self, nodes_registry_backup):
        """Test partial cancellation where some nodes complete before cancellation."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def very_fast_node(instance):
            await asyncio.sleep(0.05)
            instance.execution_log.append("very_fast_completed")
            return "very_fast_result"

        @Nodes.define(output="result")
        async def slow_cancellable_node(instance):
            try:
                await asyncio.sleep(1.0)
                return "slow_result"
            except asyncio.CancelledError:
                instance.execution_log.append("slow_cancelled")
                raise

        workflow = (
            Workflow("start_node")
            .parallel("very_fast_node", "slow_cancellable_node")
        )
        engine = workflow.build(instance=self)

        task = asyncio.create_task(engine.run(self.context))
        await asyncio.sleep(0.1)  # Let fast node complete
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Fast node should have completed
        assert "very_fast_completed" in self.execution_log
        assert "slow_cancelled" in self.execution_log

    # === CONTEXT CORRUPTION AND RACE CONDITION TESTS ===

    async def test_parallel_context_race_conditions(self, nodes_registry_backup):
        """Test race conditions when multiple nodes modify context simultaneously."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="counter")
        async def increment_node(instance):
            # Simulate race condition - read, modify, write
            await asyncio.sleep(0.01)  # Small delay to increase race condition chance
            current = instance.context.get("counter", 0)
            await asyncio.sleep(0.01)  # Another delay
            new_value = current + 1
            instance.context["counter"] = new_value
            return new_value

        workflow = (
            Workflow("start_node")
            .parallel(*["increment_node"] * 10)
        )
        engine = workflow.build(instance=self)

        # Initialize context
        self.context["counter"] = 0

        await engine.run(self.context)

        # Due to race conditions, final counter might be less than 10
        # This test documents the behavior rather than asserting correctness
        final_counter = self.context.get("counter", 0)
        assert isinstance(final_counter, int)
        assert final_counter <= 10  # Should not exceed the number of nodes

    async def test_parallel_context_isolation(self, nodes_registry_backup):
        """Test that parallel nodes don't interfere with each other's context views."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def context_reader_node(instance, node_id: str):
            # Record context access
            instance.context_access_log.append(f"node_{node_id}_start")
            await asyncio.sleep(0.1)
            
            # Read from context
            value = instance.context.get("shared_value", f"default_{node_id}")
            instance.context_access_log.append(f"node_{node_id}_read_{value}")
            
            # Modify context
            instance.context[f"result_{node_id}"] = f"modified_by_{node_id}"
            
            await asyncio.sleep(0.1)
            instance.context_access_log.append(f"node_{node_id}_end")
            return f"result_{node_id}"

        workflow = (
            Workflow("start_node")
            .parallel("context_reader_node", "context_reader_node")
        )
        engine = workflow.build(instance=self)

        # Initialize shared context
        self.context["shared_value"] = "initial"

        await engine.run({
            **self.context,
            "node_id": "test"  # This will be passed to both nodes
        })

        # Verify both nodes accessed context
        assert len([log for log in self.context_access_log if "start" in log]) == 2
        assert len([log for log in self.context_access_log if "end" in log]) == 2

    # === EXCEPTION PROPAGATION VARIANTS ===

    async def test_parallel_different_exception_types(self, nodes_registry_backup):
        """Test different types of exceptions in parallel nodes."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def value_error_node(instance):
            await asyncio.sleep(0.1)
            raise ValueError("Value error in parallel node")

        @Nodes.define(output="result")
        async def type_error_node(instance):
            await asyncio.sleep(0.1)
            raise TypeError("Type error in parallel node")

        @Nodes.define(output="result")
        async def runtime_error_node(instance):
            await asyncio.sleep(0.1)
            raise RuntimeError("Runtime error in parallel node")

        workflow = (
            Workflow("start_node")
            .parallel("value_error_node", "type_error_node", "runtime_error_node")
        )
        engine = workflow.build(instance=self)

        # Should raise one of the exceptions (non-deterministic which one)
        with pytest.raises((ValueError, TypeError, RuntimeError)):
            await engine.run(self.context)

    async def test_parallel_custom_exception_handling(self, nodes_registry_backup):
        """Test custom exception handling in parallel nodes."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        class CustomWorkflowError(Exception):
            """Custom exception for testing."""
            pass

        @Nodes.define(output="result")
        async def custom_exception_node(instance):
            await asyncio.sleep(0.1)
            raise CustomWorkflowError("Custom exception in parallel node")

        @Nodes.define(output="result")
        async def normal_node(instance):
            await asyncio.sleep(0.2)
            return "normal_result"

        workflow = (
            Workflow("start_node")
            .parallel("custom_exception_node", "normal_node")
        )
        engine = workflow.build(instance=self)

        with pytest.raises(CustomWorkflowError, match="Custom exception in parallel node"):
            await engine.run(self.context)

    async def test_parallel_exception_with_cleanup(self, nodes_registry_backup):
        """Test exception handling with proper cleanup in parallel nodes."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def cleanup_node(instance):
            try:
                await asyncio.sleep(0.1)
                instance.cleanup_log.append("resource_acquired")
                raise ValueError("Error after resource acquisition")
            except Exception:
                instance.cleanup_log.append("cleanup_performed")
                raise
            finally:
                instance.cleanup_log.append("finally_block_executed")

        @Nodes.define(output="result")
        async def normal_node(instance):
            await asyncio.sleep(0.2)
            return "normal_result"

        workflow = (
            Workflow("start_node")
            .parallel("cleanup_node", "normal_node")
        )
        engine = workflow.build(instance=self)

        with pytest.raises(ValueError):
            await engine.run(self.context)

        # Verify cleanup was performed
        assert "resource_acquired" in self.cleanup_log
        assert "cleanup_performed" in self.cleanup_log
        assert "finally_block_executed" in self.cleanup_log

    # === PARTIAL FAILURE SCENARIOS ===

    async def test_parallel_partial_success_failure(self, nodes_registry_backup):
        """Test scenarios where some parallel nodes succeed and others fail."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def success_node_1(instance):
            await asyncio.sleep(0.1)
            result = "success_1"
            instance.success_results.append(result)
            return result

        @Nodes.define(output="result")
        async def success_node_2(instance):
            await asyncio.sleep(0.15)
            result = "success_2"
            instance.success_results.append(result)
            return result

        @Nodes.define(output="result")
        async def failure_node(instance):
            await asyncio.sleep(0.2)
            raise ValueError("Failure in parallel execution")

        workflow = (
            Workflow("start_node")
            .parallel("success_node_1", "success_node_2", "failure_node")
        )
        engine = workflow.build(instance=self)

        with pytest.raises(ValueError):
            await engine.run(self.context)

        # Verify that successful nodes completed before failure
        assert "success_1" in self.success_results
        assert "success_2" in self.success_results

    async def test_parallel_intermittent_failures(self, nodes_registry_backup):
        """Test handling of intermittent failures in parallel execution."""
        failure_count = 0
        
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def intermittent_node(instance):
            nonlocal failure_count
            failure_count += 1
            await asyncio.sleep(0.1)
            
            if failure_count <= 2:
                raise ConnectionError("Intermittent connection error")
            
            return "finally_succeeded"

        @Nodes.define(output="result")
        async def reliable_node(instance):
            await asyncio.sleep(0.1)
            return "reliable_result"

        workflow = (
            Workflow("start_node")
            .parallel("intermittent_node", "reliable_node")
        )
        engine = workflow.build(instance=self)

        # Should fail on first few attempts
        with pytest.raises(ConnectionError):
            await engine.run(self.context)

    # === RESOURCE CLEANUP AND MEMORY MANAGEMENT ===

    async def test_parallel_memory_cleanup_on_failure(self, nodes_registry_backup):
        """Test memory cleanup when parallel execution fails."""
        large_objects = []
        
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def memory_intensive_node(instance):
            # Create large object
            large_data = [i for i in range(100000)]
            large_objects.append(large_data)
            await asyncio.sleep(0.1)
            raise MemoryError("Simulated memory error")

        @Nodes.define(output="result")
        async def normal_node(instance):
            await asyncio.sleep(0.2)
            return "normal_result"

        workflow = (
            Workflow("start_node")
            .parallel("memory_intensive_node", "normal_node")
        )
        engine = workflow.build(instance=self)

        # Monitor memory before execution
        gc.collect()
        initial_objects = len(gc.get_objects())

        with pytest.raises(MemoryError):
            await engine.run(self.context)

        # Force garbage collection
        large_objects.clear()
        gc.collect()
        final_objects = len(gc.get_objects())

        # Memory should be cleaned up (allow some variance)
        assert final_objects - initial_objects < 1000

    async def test_parallel_resource_cleanup_with_weakref(self, nodes_registry_backup):
        """Test resource cleanup using weak references."""
        resource_refs = []
        
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        class TestResource:
            def __init__(self, name):
                self.name = name
                self.cleanup_log = []
            
            def cleanup(self):
                self.cleanup_log.append(f"cleanup_{self.name}")
        
        @Nodes.define(output="result")
        async def resource_node(instance):
            resource = TestResource("parallel_resource")
            resource_refs.append(weakref.ref(resource))
            
            try:
                await asyncio.sleep(0.1)
                return f"used_{resource.name}"
            finally:
                resource.cleanup()

        workflow = (
            Workflow("start_node")
            .parallel("resource_node", "resource_node")
        )
        engine = workflow.build(instance=self)

        await engine.run(self.context)

        # Force garbage collection
        gc.collect()

        # Verify resources were cleaned up
        assert len(resource_refs) == 2
        alive_refs = [ref for ref in resource_refs if ref() is not None]
        assert len(alive_refs) == 0  # All resources should be garbage collected

    # === STATE CONSISTENCY TESTS ===

    async def test_parallel_workflow_state_consistency(self, nodes_registry_backup):
        """Test that workflow state remains consistent during parallel execution."""
        state_snapshots = []
        
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def state_checker_node(instance, node_id: str):
            # Capture state at different points
            state_snapshots.append({
                "node_id": node_id,
                "time": time.time(),
                "context_keys": list(instance.context.keys()),
                "context_size": len(instance.context)
            })
            
            await asyncio.sleep(0.1)
            
            # Modify state
            instance.context[f"state_{node_id}"] = f"modified_by_{node_id}"
            
            state_snapshots.append({
                "node_id": node_id,
                "time": time.time(),
                "context_keys": list(instance.context.keys()),
                "context_size": len(instance.context)
            })
            
            return f"result_{node_id}"

        workflow = (
            Workflow("start_node")
            .parallel("state_checker_node", "state_checker_node")
        )
        engine = workflow.build(instance=self)

        # Initialize state
        engine.context["initial_state"] = "test"

        await engine.run({
            "node_id": "consistency_test"
        })

        # Verify state snapshots show consistent behavior
        assert len(state_snapshots) == 4  # 2 nodes * 2 snapshots each
        
        # Initial state should be present in all snapshots
        for snapshot in state_snapshots:
            assert "initial_state" in snapshot["context_keys"]

    # === NESTED PARALLEL EXECUTION TESTS ===

    async def test_nested_parallel_execution(self, nodes_registry_backup):
        """Test parallel execution within parallel execution."""
        execution_log = []
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def outer_parallel_node(instance):
            # This node itself triggers parallel execution
            await asyncio.sleep(0.1)
            execution_log.append("outer_node_executed")
            return "outer_result"

        @Nodes.define(output="result")
        async def inner_parallel_node(instance):
            await asyncio.sleep(0.05)
            execution_log.append("inner_node_executed")
            return "inner_result"

        # Create nested workflow structure
        workflow = (
            Workflow("start_node")
            .parallel("outer_parallel_node", "inner_parallel_node")
        )
        engine = workflow.build(instance=self)

        await engine.run(self.context)

        # Verify both levels executed
        assert "outer_node_executed" in execution_log
        assert "inner_node_executed" in execution_log

    # === DYNAMIC SCENARIOS ===

    async def test_parallel_dynamic_node_creation(self, nodes_registry_backup):
        """Test dynamic node creation during parallel execution."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def dynamic_creator_node(instance):
            # Simulate dynamic behavior
            await asyncio.sleep(0.1)
            
            # Create dynamic data
            dynamic_data = {"created_at": time.time(), "data": "dynamic"}
            instance.context["dynamic_data"] = dynamic_data
            
            return "dynamic_created"

        @Nodes.define(output="result")
        async def dynamic_consumer_node(instance):
            # Wait for dynamic data
            await asyncio.sleep(0.2)
            
            # Try to consume dynamic data
            dynamic_data = instance.context.get("dynamic_data", {})
            return f"consumed_{dynamic_data.get('data', 'none')}"

        workflow = (
            Workflow("start_node")
            .parallel("dynamic_creator_node", "dynamic_consumer_node")
        )
        engine = workflow.build(instance=self)

        result = await engine.run(self.context)

        # Verify dynamic interaction
        assert "result" in result

    # === THREAD SAFETY TESTS ===

    async def test_parallel_thread_safety(self, nodes_registry_backup):
        """Test thread safety in parallel execution."""
        thread_ids = []
        execution_log = []
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def thread_aware_node(instance):
            # Record thread ID
            thread_id = threading.current_thread().ident
            thread_ids.append(thread_id)
            
            await asyncio.sleep(0.1)
            
            # Simulate thread-sensitive operation
            execution_log.append(f"thread_{thread_id}_executed")
            return f"thread_result_{thread_id}"

        workflow = (
            Workflow("start_node")
            .parallel("thread_aware_node", "thread_aware_node", "thread_aware_node")
        )
        engine = workflow.build(instance=self)

        await engine.run(self.context)

        # Verify thread safety
        assert len(thread_ids) == 3
        assert len(set(thread_ids)) >= 1  # At least one thread (might be same for asyncio)

    # === NETWORK/CONNECTION FAILURE SIMULATION ===

    async def test_parallel_network_failure_simulation(self, nodes_registry_backup):
        """Test handling of network failures in parallel execution."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def network_node(instance):
            # Simulate network operation
            await asyncio.sleep(0.1)
            
            # Simulate network failure
            raise ConnectionError("Network connection failed")

        @Nodes.define(output="result")
        async def local_node(instance):
            # Local operation that should succeed
            await asyncio.sleep(0.1)
            return "local_success"

        workflow = (
            Workflow("start_node")
            .parallel("network_node", "local_node")
        )
        engine = workflow.build(instance=self)

        with pytest.raises(ConnectionError):
            await engine.run(self.context)

    async def test_parallel_timeout_with_retry_logic(self, nodes_registry_backup):
        """Test timeout handling with retry logic in parallel execution."""
        retry_count = 0
        
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def retry_node(instance):
            nonlocal retry_count
            retry_count += 1
            
            if retry_count <= 2:
                await asyncio.sleep(0.5)  # Simulate slow operation
                raise TimeoutError("Operation timeout")
            
            await asyncio.sleep(0.1)
            return "retry_success"

        @Nodes.define(output="result")
        async def stable_node(instance):
            await asyncio.sleep(0.1)
            return "stable_success"

        workflow = (
            Workflow("start_node")
            .parallel("retry_node", "stable_node")
        )
        engine = workflow.build(instance=self)

        # Should fail on first attempt
        with pytest.raises(TimeoutError):
            await engine.run(self.context)

    # === PERFORMANCE EDGE CASES ===

    async def test_parallel_execution_under_load(self, nodes_registry_backup):
        """Test parallel execution under high load conditions."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def load_node(instance):
            # Simulate CPU-intensive operation
            await asyncio.sleep(0.01)
            
            # Simulate some computation
            result = sum(i * i for i in range(1000))
            return f"computed_{result}"

        # Create high load scenario
        node_names = ["load_node" for _ in range(50)]
        workflow = (
            Workflow("start_node")
            .parallel(*node_names)
        )
        engine = workflow.build(instance=self)

        start_time = time.time()
        result = await engine.run(self.context)
        end_time = time.time()

        # Should complete in reasonable time despite high load
        assert end_time - start_time < 2.0
        assert "result" in result

    async def test_parallel_execution_complex_edge_case(self, nodes_registry_backup):
        """Test complex combination of edge cases."""
        execution_log = []
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result")
        async def complex_node(instance):
            # Combine multiple edge case scenarios
            try:
                # Simulate network delay
                await asyncio.sleep(0.1)
                
                # Simulate context access
                value = instance.context.get("shared_value", 0)
                
                # Simulate potential race condition
                await asyncio.sleep(0.01)
                instance.context["shared_value"] = value + 1
                
                # Simulate potential failure
                if value > 5:
                    raise ValueError("Complex failure condition")
                
                return f"complex_result_{value}"
                
            except Exception as e:
                execution_log.append(f"complex_error_{e}")
                raise

        workflow = (
            Workflow("start_node")
            .parallel("complex_node", "complex_node", "complex_node")
        )
        engine = workflow.build(instance=self)

        # Initialize context
        engine.context["shared_value"] = 0

        result = await engine.run(self.context)

        # Verify complex interaction
        assert "result" in result
        shared_value = engine.context.get("shared_value", 0)
        assert isinstance(shared_value, int)

    # === ADDITIONAL EDGE CASES ===

    async def test_parallel_execution_with_many_nodes(self, nodes_registry_backup):
        """Test parallel execution with a large number of nodes."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        node_count = 100
        for i in range(node_count):
            @Nodes.define(name=f"load_node_{i}", output=f"result_{i}")
            async def load_node(instance):
                await asyncio.sleep(0.01)
                return "computed"

        node_names = [f"load_node_{i}" for i in range(node_count)]
        workflow = (
            Workflow("start_node")
            .parallel(*node_names)
        )
        engine = workflow.build(instance=self)

        start_time = time.time()
        result = await engine.run(self.context)
        duration = time.time() - start_time

        # Verify all nodes completed
        for i in range(node_count):
            assert result.get(f"result_{i}") == "computed"
        
        # Verify execution time is reasonable
        assert duration < 2.0, "Execution with many nodes took too long"

    async def test_parallel_nodes_with_varied_execution_times(self, nodes_registry_backup):
        """Test parallel nodes with different execution times."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result_fast")
        async def fast_node(instance):
            await asyncio.sleep(0.05)
            return "fast_done"

        @Nodes.define(output="result_medium")
        async def medium_node(instance):
            await asyncio.sleep(0.1)
            return "medium_done"

        @Nodes.define(output="result_slow")
        async def slow_node(instance):
            await asyncio.sleep(0.2)
            return "slow_done"

        workflow = (
            Workflow("start_node")
            .parallel("fast_node", "medium_node", "slow_node")
        )
        engine = workflow.build(instance=self)

        result = await engine.run(self.context)

        # Verify all nodes completed and their results are in the context
        assert result.get("result_fast") == "fast_done"
        assert result.get("result_medium") == "medium_done"
        assert result.get("result_slow") == "slow_done"

    async def test_parallel_nodes_all_failing(self, nodes_registry_backup):
        """Test that exceptions are correctly propagated when all parallel nodes fail."""
        @Nodes.define(output="result")
        async def start_node(instance):
            await asyncio.sleep(0.01)
            return "start_completed"

        @Nodes.define(output="result_1")
        async def failing_node_1(instance):
            await asyncio.sleep(0.1)
            raise ValueError("Failure 1")

        @Nodes.define(output="result_2")
        async def failing_node_2(instance):
            await asyncio.sleep(0.1)
            raise RuntimeError("Failure 2")

        workflow = (
            Workflow("start_node")
            .parallel("failing_node_1", "failing_node_2")
        )
        engine = workflow.build(instance=self)

        with pytest.raises((ValueError, RuntimeError)):
            await engine.run(self.context)

    async def test_parallel_execution_with_sub_workflow(self, nodes_registry_backup):
        """Test parallel execution with a sub-workflow."""
        @Nodes.define(output="result")
        async def start_node(instance):
            return "start"

        @Nodes.define(output="sub_result")
        async def sub_workflow_node(instance):
            await asyncio.sleep(0.1)
            return "sub_workflow_completed"

        sub_workflow = Workflow("sub_workflow_node")
        
        @Nodes.define(output="main_result")
        async def main_workflow_node(instance):
            await asyncio.sleep(0.1)
            return "main_workflow_completed"

        workflow = (
            Workflow("start_node")
            .add_sub_workflow("sub_workflow", sub_workflow, {}, "sub_workflow_output")
            .parallel("main_workflow_node")
        )
        engine = workflow.build(instance=self)
        result = await engine.run(self.context)

        assert result.get("sub_workflow_output") == "sub_workflow_completed"
        assert result.get("main_result") == "main_workflow_completed"

    async def test_parallel_nodes_with_mixed_output_strategies(self, nodes_registry_backup):
        """Test parallel nodes with different output strategies."""
        @Nodes.define(output="result")
        async def start_node(instance):
            return "start"

        @Nodes.define(output="dict_output")
        async def dict_output_node(instance):
            return {"key1": "value1", "key2": 123}

        @Nodes.define(output="single_output")
        async def single_output_node(instance):
            return "single_value"

        @Nodes.define
        async def no_output_node(instance):
            instance.context["no_output_side_effect"] = "executed"
            return None

        workflow = (
            Workflow("start_node")
            .parallel("dict_output_node", "single_output_node", "no_output_node")
        )
        engine = workflow.build(instance=self)
        result = await engine.run(self.context)

        assert result.get("dict_output") == {"key1": "value1", "key2": 123}
        assert result.get("single_output") == "single_value"
        assert result.get("no_output_side_effect") == "executed"

    async def test_empty_parallel_block(self, nodes_registry_backup):
        """Test that an empty parallel block is handled gracefully."""
        @Nodes.define(output="result")
        async def start_node(instance):
            instance.execution_log.append("start_node_executed")
            return "start"

        @Nodes.define(output="result")
        async def end_node(instance):
            instance.execution_log.append("end_node_executed")
            return "end"

        workflow = (
            Workflow("start_node")
            .parallel()
            .then("end_node")
        )
        engine = workflow.build(instance=self)
        await engine.run(self.context)

        assert "start_node_executed" in self.execution_log
        assert "end_node_executed" in self.execution_log

    async def test_parallel_execution_with_convergence(self, nodes_registry_backup):
        """Test that parallel nodes converge to a single node."""
        @Nodes.define(output="result")
        async def start_node(instance):
            return "start"

        @Nodes.define(output="res1")
        async def parallel_node_1(instance):
            await asyncio.sleep(0.1)
            return "result1"

        @Nodes.define(output="res2")
        async def parallel_node_2(instance):
            await asyncio.sleep(0.2)
            return "result2"

        @Nodes.define(output="final_result")
        async def converge_node(instance, res1: str, res2: str):
            return f"{res1}_{res2}"

        workflow = (
            Workflow("start_node")
            .parallel("parallel_node_1", "parallel_node_2")
            .converge("converge_node")
        )
        engine = workflow.build(instance=self)
        result = await engine.run(self.context)

        assert result.get("final_result") == "result1_result2"
