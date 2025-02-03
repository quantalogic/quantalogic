'use client';

import { useState, useEffect, useRef } from 'react'; 
import { marked } from 'marked';
import Prism from 'prismjs';
import { EventVisualizer } from '@/components/EventVisualizer';
import { useEventSource } from '@/hooks/useEventSource';

interface TaskSubmission {
  task: string;
  model_name?: string;
  max_iterations?: number;
}

export default function Home() {
  const [model, setModel] = useState('openrouter/deepseek/deepseek-chat');
  const [maxIterations, setMaxIterations] = useState(30);
  const [taskInput, setTaskInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const eventsContainerRef = useRef<HTMLDivElement>(null);

  const { events, error, isConnected, clearEvents } = useEventSource(
    //process.env.NEXT_PUBLIC_API_URL || 
    'http://localhost:8000',
    { taskId: currentTaskId || undefined }
  );

  const handleSubmit = async () => {
    try {
      setIsSubmitting(true);
      clearEvents();

      const submission: TaskSubmission = {
        task: taskInput,
        model_name: model,
        max_iterations: maxIterations,
      };

      console.log('Submitting task:', submission);
      const response = await fetch('http://localhost:8000/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(submission),
      });

      console.log('Response status:', response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        throw new Error('Failed to submit task');
      }

      const responseData = await response.json();
      console.log('Task submission response:', responseData);
      const { task_id } = responseData;
      console.log('Setting task ID:', task_id);
      setCurrentTaskId(task_id);
    } catch (error) {
      console.error('Error submitting task:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    // Auto-scroll logic
    if (autoScroll && eventsContainerRef.current) {
      eventsContainerRef.current.scrollTop = eventsContainerRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const copyAnswer = () => {
    if (events && events.length > 0) {
      navigator.clipboard.writeText(events[events.length - 1].message);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 py-2">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-3">
              <h1 className="text-lg font-semibold text-gray-900">QuantaLogic</h1>
              <span className="text-sm text-gray-500">AI Assistant</span>
            </div>
            <div className="flex items-center space-x-3">
              <select 
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="block w-48 text-sm rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              >
                <option value="openrouter/deepseek/deepseek-chat">DeepSeek Chat</option>
                <option value="ollama/qwen2.5-coder:14b">Qwen Coder</option>
                <option value="gpt-4o-mini">gpt-4o-mini</option>
              </select>
              <div className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${
                isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex min-h-0">
        {/* Left Panel - Task Input */}
        <div className="w-1/2 p-4 flex flex-col min-h-0">
          <div className="bg-white rounded-lg shadow-sm p-4 flex flex-col flex-1">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Task Input</h2>
              <div className="flex items-center space-x-4">
                <label className="flex items-center space-x-2">
                  <span className="text-sm text-gray-600">Max Iterations:</span>
                  <input
                    type="number"
                    value={maxIterations}
                    onChange={(e) => setMaxIterations(Number(e.target.value))}
                    className="w-20 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    min={1}
                    max={100}
                  />
                </label>
              </div>
            </div>
            <textarea
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              className="flex-1 p-4 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm resize-none"
              placeholder="Describe your task here..."
            />
            <div className="mt-4 flex justify-end">
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>Submit Task</span>
                {isSubmitting && (
                  <div className="ml-2">
                    <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </div>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel - Events and Results */}
        <div className="w-1/2 p-4 flex flex-col min-h-0">
          <div className="bg-white rounded-lg shadow-sm p-4 flex flex-col flex-1 overflow-hidden">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Events & Results</h2>
              <div className="flex items-center space-x-4">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={autoScroll}
                    onChange={(e) => setAutoScroll(e.target.checked)}
                    className="rounded text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-600">Auto-scroll</span>
                </label>
                <button
                  onClick={clearEvents}
                  className="inline-flex items-center px-3 py-1 text-sm text-gray-600 hover:text-gray-900 focus:outline-none"
                >
                  Clear
                </button>
                <button
                  onClick={copyAnswer}
                  className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-md text-green-700 bg-green-100 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                  <svg className="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                  </svg>
                  <span>Copy</span>
                </button>
              </div>
            </div>
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
              {/* Events Container */}
              <div ref={eventsContainerRef} className="flex-1 overflow-y-auto space-y-2 min-h-0 mb-4">
                <EventVisualizer events={events} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
