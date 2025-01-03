import { EventVisualizer } from './event_visualizer.js';

class QuantaLogicUI {
    constructor() {
        this.eventSource = null;
        this.isProcessing = false;
        this.eventVisualizer = new EventVisualizer();
        this.processedEventIds = new Set();
        this.activeValidationDialog = null;
        this.connectionState = 'disconnected';
        this.initializeElements();
        this.attachEventListeners();
        this.connectSSE();
        this.currentTaskId = null;  // Add tracking for current task
    }

    initializeElements() {
        this.elements = {
            taskInput: document.getElementById('taskInput'),
            submitTask: document.getElementById('submitTask'),
            clearEvents: document.getElementById('clearEvents'),
            eventsContainer: document.getElementById('eventsContainer'),
            connectionStatus: document.getElementById('connectionStatus'),
            modelSelect: document.getElementById('modelSelect'),
            maxIterations: document.getElementById('maxIterations'),
            autoScroll: document.getElementById('autoScroll'),
            finalAnswer: document.getElementById('finalAnswer'),
            copyAnswer: document.getElementById('copyAnswer')
        };

        // Verify elements exist and throw error if critical elements are missing
        if (!this.elements.eventsContainer || !this.elements.clearEvents) {
            console.error('Critical UI elements are missing');
        }
    }

    attachEventListeners() {
        // Task submission handlers
        this.elements.submitTask.addEventListener('click', () => this.handleTaskSubmit());
        this.elements.taskInput.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.handleTaskSubmit();
            }
        });

        // Clear events handler
        this.elements.clearEvents.addEventListener('click', () => this.clearEvents());

        // Copy answer handler
        this.elements.copyAnswer?.addEventListener('click', () => this.handleCopyAnswer());
    }

    connectSSE() {
        if (this.eventSource) {
            this.eventSource.close();
            this.processedEventIds.clear();
        }

        this.eventSource = new EventSource('/events');

        this.eventSource.onopen = () => {
            this.updateConnectionStatus(true);
            console.log('SSE Connection established');
        };

        // Standard event handlers
        const eventTypes = [
            'session_start', 'session_end', 'session_add_message',
            'task_solve_start', 'task_solve_end',
            'task_think_start', 'task_think_end', 'task_complete',
            'tool_execution_start', 'tool_execution_end',
            'tool_execute_validation_start', 'tool_execute_validation_end',
            'memory_full', 'memory_compacted', 'memory_summary',
            'error_max_iterations_reached', 'error_tool_execution',
            'error_model_response', 'final_result', 'error'
        ];

        eventTypes.forEach(eventType => {
            this.eventSource.addEventListener(eventType, (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (!data.id || !this.processedEventIds.has(data.id)) {
                        this.handleEvent(data);
                    }
                } catch (error) {
                    console.error(`Error handling ${eventType} event:`, error);
                }
            });
        });

        // Validation request handler
        this.eventSource.addEventListener('user_validation_request', async (event) => {
            try {
                const data = JSON.parse(event.data);
                const validationData = data.data;
                const response = await this.showValidationDialog(validationData.question);
                await this.submitValidationResponse(validationData.validation_id, response);
            } catch (error) {
                console.error('Error handling validation request:', error);
            }
        });

        this.eventSource.onerror = (error) => {
            console.error('SSE Error:', error);
            this.updateConnectionStatus(false);
            this.eventSource.close();
            setTimeout(() => this.connectSSE(), 5000);
        };
    }

    async handleTaskSubmit() {
        if (this.isProcessing) {
            this.showNotification('Please wait for the current task to complete.', 'warning');
            return;
        }

        const task = this.elements.taskInput.value.trim();
        if (!task) {
            this.showNotification('Please enter a task.', 'warning');
            return;
        }

        this.clearEvents();
        this.setProcessingState(true);

        try {
            // Submit task using new endpoint
            const submitResponse = await fetch('/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    task: task,
                    model_name: this.elements.modelSelect.value,
                    max_iterations: parseInt(this.elements.maxIterations.value)
                }),
            });

            if (!submitResponse.ok) {
                throw new Error('Failed to submit task');
            }

            const { task_id } = await submitResponse.json();
            this.currentTaskId = task_id;  // Set current task ID

            // Start polling for task status
            await this.pollTaskStatus(task_id);

            // Initialize Event Stream with task_id
            this.initializeEventStream(task_id);

        } catch (error) {
            console.error('Error:', error);
            this.handleEvent({
                event: 'error',
                timestamp: new Date().toISOString(),
                data: {
                    error: error.message
                }
            });
        } finally {
            this.setProcessingState(false);
            this.currentTaskId = null;  // Clear task ID when done
        }
    }

    initializeEventStream(taskId) {
        // Close existing event source if any
        if (this.eventSource) {
            this.eventSource.close();
        }

        // Reset connection state
        this.connectionState = 'connecting';
        this.updateConnectionStatus();

        // Initialize a new EventSource with task_id
        this.eventSource = new EventSource(`/events?task_id=${taskId}`);

        this.eventSource.onopen = () => {
            this.connectionState = 'connected';
            this.updateConnectionStatus();
            console.log(`Connected to event stream for task ${taskId}`);
        };

        this.eventSource.onmessage = (event) => {
            try {
                const eventData = JSON.parse(event.data);
                this.displayEvent(eventData);
            } catch (parseError) {
                console.error('Error parsing event data:', parseError);
            }
        };

        this.eventSource.addEventListener('task_complete', (event) => {
            const data = JSON.parse(event.data);
            console.log(`Task ${data.task_id} completed with result:`, data.result);
            this.closeEventStream();
        });

        this.eventSource.addEventListener('task_error', (event) => {
            const data = JSON.parse(event.data);
            console.error(`Task ${data.task_id} failed with error:`, data.error);
            this.closeEventStream();
        });

        this.eventSource.onerror = (error) => {
            this.connectionState = 'disconnected';
            this.updateConnectionStatus();
            console.error('EventSource failed:', error);
            
            // Attempt reconnection with exponential backoff
            this.reconnectEventStream(taskId);
        };
    }

    closeEventStream() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.connectionState = 'disconnected';
        this.updateConnectionStatus();
    }

    reconnectEventStream(taskId, attempt = 1) {
        const maxAttempts = 5;
        const baseDelay = 1000; // 1 second
        
        if (attempt > maxAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        const delay = baseDelay * Math.pow(2, attempt - 1);
        
        setTimeout(() => {
            console.log(`Attempting to reconnect (Attempt ${attempt})...`);
            this.initializeEventStream(taskId);
        }, delay);
    }

    updateConnectionStatus() {
        const statusElement = document.getElementById('connectionStatus');
        if (statusElement) {
            statusElement.textContent = `Connection: ${this.connectionState}`;
            statusElement.className = this.connectionState;
        }
    }

    async pollTaskStatus(taskId) {
        const pollInterval = 1000; // 1 second
        const maxAttempts = 300; // 5 minutes maximum
        let attempts = 0;

        const poll = async () => {
            try {
                const response = await fetch(`/tasks/${taskId}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch task status');
                }

                const taskStatus = await response.json();

                switch (taskStatus.status) {
                    case 'completed':
                        this.handleEvent({
                            event: 'task_complete',
                            task_id: taskId,
                            timestamp: new Date().toISOString(),
                            data: {
                                result: taskStatus.result,
                                total_tokens: taskStatus.total_tokens,
                                model_name: taskStatus.model_name
                            }
                        });
                        return true;

                    case 'failed':
                        this.handleEvent({
                            event: 'error',
                            task_id: taskId,
                            timestamp: new Date().toISOString(),
                            data: {
                                error: taskStatus.error
                            }
                        });
                        return true;

                    case 'running':
                        // Continue polling
                        return false;

                    default:
                        if (++attempts >= maxAttempts) {
                            throw new Error('Task polling timeout');
                        }
                        return false;
                }
            } catch (error) {
                console.error('Polling error:', error);
                this.handleEvent({
                    event: 'error',
                    task_id: taskId,
                    timestamp: new Date().toISOString(),
                    data: {
                        error: error.message
                    }
                });
                return true;
            }
        };

        while (!(await poll())) {
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
    }

    setProcessingState(processing) {
        this.isProcessing = processing;
        this.elements.submitTask.disabled = processing;

        const buttonText = this.elements.submitTask.querySelector('span');
        const loadingIndicator = this.elements.submitTask.querySelector('.loading-indicator');

        if (processing) {
            buttonText.textContent = 'Processing...';
            loadingIndicator?.classList.remove('hidden');
            this.elements.submitTask.classList.add('opacity-75');
        } else {
            buttonText.textContent = 'Submit Task';
            loadingIndicator?.classList.add('hidden');
            this.elements.submitTask.classList.remove('opacity-75');
        }
    }

    async showValidationDialog(question) {
        if (this.activeValidationDialog) {
            this.closeValidationDialog();
        }

        return new Promise((resolve) => {
            const dialog = document.createElement('div');
            dialog.className = 'fixed inset-0 z-50 overflow-y-auto';
            dialog.setAttribute('role', 'dialog');
            dialog.setAttribute('aria-modal', 'true');

            dialog.innerHTML = `
                <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
                    <div class="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" aria-hidden="true"></div>
                    <span class="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
                    <div class="inline-block px-4 pt-5 pb-4 overflow-hidden text-left align-bottom transition-all transform bg-white rounded-lg shadow-xl sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
                        <div class="sm:flex sm:items-start">
                            <div class="flex items-center justify-center flex-shrink-0 w-12 h-12 mx-auto bg-blue-100 rounded-full sm:mx-0 sm:h-10 sm:w-10">
                                <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                                <h3 class="text-lg font-medium leading-6 text-gray-900">Validation Required</h3>
                                <div class="mt-2">
                                    <p class="text-sm text-gray-500">${question}</p>
                                </div>
                            </div>
                        </div>
                        <div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                            <button type="button" class="validate-yes inline-flex justify-center w-full px-4 py-2 text-base font-medium text-white bg-blue-600 border border-transparent rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm">
                                Yes
                            </button>
                            <button type="button" class="validate-no mt-3 inline-flex justify-center w-full px-4 py-2 text-base font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:w-auto sm:text-sm">
                                No
                            </button>
                        </div>
                    </div>
                </div>
            `;

            const handleResponse = (response) => {
                this.closeValidationDialog();
                resolve(response);
            };

            dialog.querySelector('.validate-yes').addEventListener('click', () => handleResponse(true));
            dialog.querySelector('.validate-no').addEventListener('click', () => handleResponse(false));

            document.body.appendChild(dialog);
            this.activeValidationDialog = dialog;
        });
    }

    closeValidationDialog() {
        if (this.activeValidationDialog) {
            document.body.removeChild(this.activeValidationDialog);
            this.activeValidationDialog = null;
        }
    }

    async submitValidationResponse(validationId, response) {
        try {
            const result = await fetch(`/validate_response/${validationId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ response })
            });

            if (!result.ok) {
                throw new Error('Failed to submit validation response');
            }

            return await result.json();
        } catch (error) {
            console.error('Error submitting validation response:', error);
            throw error;
        }
    }

    handleEvent(eventData) {
        try {
            // Only process events for the current task or events without task_id
            if (eventData.task_id && eventData.task_id !== this.currentTaskId) {
                return;
            }

            if (eventData.id && this.processedEventIds.has(eventData.id)) {
                return;
            }

            this.addEvent(eventData);

            if (eventData.id) {
                this.processedEventIds.add(eventData.id);

                if (this.processedEventIds.size > 1000) {
                    const idsArray = Array.from(this.processedEventIds);
                    this.processedEventIds = new Set(idsArray.slice(-500));
                }
            }

            // Update final answer without clearing events
            if ((eventData.event === 'final_result' || eventData.event === 'task_complete') && 
                (!eventData.task_id || eventData.task_id === this.currentTaskId)) {
                this.displayFinalAnswer(eventData.data);
            }
        } catch (error) {
            console.error('Error handling event:', error);
        }
    }

    addEvent(eventData) {
        const eventElement = this.eventVisualizer.createEventCard(eventData);
        if (!eventElement) return;

        // Remove running state from previous event if it exists
        if (this.lastRunningEvent) {
            this.eventVisualizer.updateRunningState(this.lastRunningEvent, false);
        }

        this.elements.eventsContainer.appendChild(eventElement);

        // Update running state tracking
        const isRunning = this.eventVisualizer.isRunningEvent(eventData.event || eventData.type);
        if (isRunning) {
            this.lastRunningEvent = eventElement;
        } else if (this.lastRunningEvent) {
            // If this is an "end" event that matches the last running event's type
            const lastRunningType = this.lastRunningEvent.querySelector('.font-medium').textContent;
            const currentType = eventData.event || eventData.type;
            if (currentType.toLowerCase().includes('end') && 
                currentType.toLowerCase().replace('_end', '').includes(lastRunningType.toLowerCase().replace('Start', ''))) {
                this.eventVisualizer.updateRunningState(this.lastRunningEvent, false);
                this.lastRunningEvent = null;
            }
        }

        if (this.elements.autoScroll.checked) {
            this.elements.eventsContainer.scrollTop = this.elements.eventsContainer.scrollHeight;
        }

        if (window.Prism) {
            Prism.highlightAllUnder(eventElement);
        }
    }

    clearEvents() {
        if (this.elements.eventsContainer) {
            while (this.elements.eventsContainer.firstChild) {
                this.elements.eventsContainer.removeChild(this.elements.eventsContainer.firstChild);
            }
        }
        this.processedEventIds.clear();
        this.clearFinalAnswer();
        this.lastRunningEvent = null;
        this.currentTaskId = null;  // Reset current task ID
    }

    clearFinalAnswer() {
        if (this.elements.finalAnswer) {
            this.elements.finalAnswer.classList.add('hidden');
            const answerContent = this.elements.finalAnswer.querySelector('.answer-content');
            if (answerContent) {
                answerContent.innerHTML = '';
            }
        }
    }

    displayFinalAnswer(data) {
        if (!this.elements.finalAnswer || !data.result) return;

        const answerContent = this.elements.finalAnswer.querySelector('.answer-content');
        if (!answerContent) return;

        // Parse markdown and render without affecting events
        const renderedContent = marked.parse(data.result, {
            highlight: (code, lang) => {
                if (Prism.languages[lang]) {
                    return Prism.highlight(code, Prism.languages[lang], lang);
                }
                return code;
            }
        });

        answerContent.innerHTML = renderedContent;
        this.elements.finalAnswer.classList.remove('hidden');

        // Apply syntax highlighting
        answerContent.querySelectorAll('pre code').forEach((block) => {
            Prism.highlightElement(block);
        });

        // Scroll to show the answer
        if (this.elements.autoScroll.checked) {
            this.elements.finalAnswer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    async handleCopyAnswer() {
        const answerContent = this.elements.finalAnswer.querySelector('.answer-content');
        if (!answerContent) return;

        try {
            await navigator.clipboard.writeText(answerContent.textContent);

            const copyButton = this.elements.copyAnswer;
            const originalText = copyButton.querySelector('span').textContent;
            const originalClasses = copyButton.className;

            copyButton.className = 'inline-flex items-center px-3 py-1 text-sm font-medium rounded-md text-green-700 bg-green-100 transition-colors duration-200';
            copyButton.querySelector('span').textContent = 'Copied!';

            setTimeout(() => {
                copyButton.className = originalClasses;
                copyButton.querySelector('span').textContent = originalText;
            }, 2000);
        } catch (error) {
            console.error('Failed to copy text:', error);
        }
    }

    showNotification(message, type = 'info') {
        // Implementation can be added for showing notifications
        console.log(`${type}: ${message}`);
    }
}

// Initialize the UI when the document is ready
document.addEventListener('DOMContentLoaded', () => {
    window.quantaLogicUI = new QuantaLogicUI();
});