import React, { useEffect } from 'react';
import { format } from 'date-fns';

interface Event {
  id: string;
  event: string;
  task_id?: string;
  data: any;
  timestamp: string;
}

interface EventVisualizerProps {
  events: Event[];
}

export const EventVisualizer: React.FC<EventVisualizerProps> = ({ events }) => {
  useEffect(() => {
    console.log('EventVisualizer received events:', events);
  }, [events]);

  const getEventColor = (eventType: string): { bg: string; text: string; border: string } => {
    const type = eventType.toLowerCase();
    if (type.includes('start')) {
      return { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' };
    } else if (type.includes('end')) {
      return { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' };
    } else if (type.includes('error')) {
      return { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' };
    } else if (type.includes('complete')) {
      return { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' };
    }
    return { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' };
  };

  const formatEventContent = (data: any): string => {
    if (typeof data === 'string') return data;
    return JSON.stringify(data, null, 2);
  };

  if (!events || events.length === 0) {
    console.log('No events to display');
    return (
      <div className="text-center py-8 text-gray-500">
        No events to display
      </div>
    );
  }

  console.log('Rendering events:', events);
  return (
    <div className="space-y-3">
      {events.map((event) => {
        console.log('Rendering event:', event);
        const colors = getEventColor(event.event);
        const formattedContent = formatEventContent(event.data);
        
        return (
          <div
            key={event.id}
            className={`p-4 rounded-lg border ${colors.bg} ${colors.border}`}
          >
            <div className="flex justify-between items-start mb-2">
              <div className={`font-medium ${colors.text}`}>
                {event.event}
              </div>
              <div className="text-sm text-gray-500">
                {format(new Date(event.timestamp), 'HH:mm:ss')}
              </div>
            </div>
            <div className="text-sm whitespace-pre-wrap font-mono">
              {formattedContent}
            </div>
          </div>
        );
      })}
    </div>
  );
};
