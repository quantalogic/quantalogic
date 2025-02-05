import { useState, useEffect, useCallback } from 'react';

interface EventSourceOptions {
  taskId?: string;
  onEvent?: (event: any) => void;
}

export const useEventSource = (baseUrl: string, options: EventSourceOptions = {}) => {
  const [events, setEvents] = useState<any[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    try {
      const url = new URL('/events', baseUrl);
      if (options.taskId) {
        url.searchParams.append('task_id', options.taskId);
      }

      console.log('Connecting to SSE:', url.toString());
      const eventSource = new EventSource(url.toString());

      eventSource.onopen = () => {
        console.log('SSE Connection opened');
        setIsConnected(true);
        setError(null);
      };

      eventSource.onerror = (error) => {
        console.error('SSE Connection error:', error);
        setIsConnected(false);
        setError(new Error('EventSource failed to connect'));
      };

      const handleEvent = (event: MessageEvent) => {
        console.log('Received event:', event.type, event.data);
        
        if (event.data === ': keepalive') {
          console.log('Received keepalive');
          return;
        }

        try {
          const parsedData = JSON.parse(event.data);
          console.log('Parsed event data:', parsedData);
          setEvents((prevEvents) => {
            const newEvents = [...prevEvents, parsedData];
            console.log('Updated events array:', newEvents);
            return newEvents;
          });
          options.onEvent?.(parsedData);
        } catch (e) {
          console.error('Failed to parse event data:', e);
        }
      };

      // Register handlers for all event types
      const eventTypes = [
        'session_start',
        'session_end',
        'session_add_message',
        'task_solve_start',
        'task_solve_end',
        'task_think_start',
        'task_think_end',
        'task_complete',
        'tool_execution_start',
        'tool_execution_end',
        'tool_execute_validation_start',
        'tool_execute_validation_end',
        'memory_full',
        'memory_compacted',
        'memory_summary',
        'error_max_iterations_reached',
        'error_tool_execution',
        'error_model_response',
        'stream_chunk',
        'stream_end',
        'stream_start'
      ];

      eventTypes.forEach((eventType) => {
        console.log('Registering handler for event type:', eventType);
        eventSource.addEventListener(eventType, handleEvent);
      });

      // Also listen for message event for any non-specific events
      eventSource.onmessage = handleEvent;

      return () => {
        console.log('Cleaning up SSE connection');
        eventSource.close();
        setIsConnected(false);
      };
    } catch (error) {
      console.error('Error in SSE setup:', error);
      setError(error as Error);
      return () => {};
    }
  }, [baseUrl, options.taskId, options.onEvent]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  return {
    events,
    error,
    isConnected,
    clearEvents: () => setEvents([]),
  };
};
