export class EventVisualizer {
    constructor() {
        this.typeStyles = {
            start: {
                border: 'border-green-500',
                bg: 'bg-green-50',
                text: 'text-green-800',
                icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z" clip-rule="evenodd"/>
                </svg>`
            },
            end: {
                border: 'border-blue-500',
                bg: 'bg-blue-50',
                text: 'text-blue-800',
                icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.707-10.293a1 1 0 00-1.414-1.414l-3 3a1 1 0 000 1.414l3 3a1 1 0 001.414-1.414L9.414 11H13a1 1 0 100-2H9.414l1.293-1.293z" clip-rule="evenodd"/>
                </svg>`
            },
            error: {
                border: 'border-red-500',
                bg: 'bg-red-50',
                text: 'text-red-800',
                icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
                </svg>`
            },
            info: {
                border: 'border-indigo-500',
                bg: 'bg-indigo-50',
                text: 'text-indigo-800',
                icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
                </svg>`
            },
            warning: {
                border: 'border-yellow-500',
                bg: 'bg-yellow-50',
                text: 'text-yellow-800',
                icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                </svg>`
            },
            validation: {
                border: 'border-purple-500',
                bg: 'bg-purple-50',
                text: 'text-purple-800',
                icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
                </svg>`
            }
        };
        this.lastRunningEvent = null;
    }

    getEventTypeInfo(type) {
        if (!type) return this.typeStyles.info;
        const lowerType = type.toLowerCase();

        for (const [key, style] of Object.entries(this.typeStyles)) {
            if (lowerType.includes(key)) {
                return style;
            }
        }

        return this.typeStyles.info;
    }

    createEventCard(event) {
        const card = document.createElement('div');
        const eventType = event.type || event.event || 'unknown';
        const typeInfo = this.getEventTypeInfo(eventType);
        const isRunning = this.isRunningEvent(eventType);

        card.dataset.running = isRunning;
        card.dataset.eventType = eventType.toLowerCase();
        
        card.className = `
            mb-4 rounded-lg shadow-sm border-l-4 ${typeInfo.border} ${typeInfo.bg} 
            transition-all duration-300 hover:shadow-md transform hover:-translate-y-px
        `;

        if (isRunning) {
            const processingIndicator = document.createElement('div');
            processingIndicator.className = 'absolute right-0 top-0 mt-4 mr-12';
            processingIndicator.innerHTML = `
                <div class="flex items-center space-x-2">
                    <span class="text-sm text-gray-500">Processing</span>
                    <svg class="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </div>
            `;
            card.classList.add('relative');
            card.insertBefore(processingIndicator, card.firstChild);
        }

        const header = this.createEventHeader(event, typeInfo);
        const contentWrapper = this.createEventContentWrapper(event, typeInfo);

        header.addEventListener('click', () => {
            contentWrapper.classList.toggle('hidden');
            header.querySelector('.expand-icon').classList.toggle('rotate-180');
        });

        card.appendChild(header);
        card.appendChild(contentWrapper);
        return card;
    }

    isRunningEvent(eventType) {
        const type = eventType.toLowerCase();
        return type.includes('start') || type.includes('running') || 
               (type.includes('think') && !type.includes('end')) ||
               (type.includes('execution') && !type.includes('end'));
    }

    updateRunningState(eventElement, isRunning) {
        if (isRunning) {
            eventElement.dataset.running = 'true';
        } else {
            eventElement.dataset.running = 'false';
        }

        // Update processing indicator
        const existingIndicator = eventElement.querySelector('.animate-spin');
        if (isRunning && !existingIndicator) {
            const processingIndicator = document.createElement('div');
            processingIndicator.className = 'absolute right-0 top-0 mt-4 mr-12';
            processingIndicator.innerHTML = `
                <svg class="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            `;
            eventElement.classList.add('relative');
            eventElement.insertBefore(processingIndicator, eventElement.firstChild);
        } else if (!isRunning && existingIndicator) {
            existingIndicator.parentElement.remove();
        }
    }

    createEventHeader(event, typeInfo) {
        const header = document.createElement('div');
        header.className = `
            flex flex-wrap items-center justify-between p-4 cursor-pointer select-none
            hover:bg-opacity-50 transition-colors duration-200 gap-2
        `;

        const leftContent = document.createElement('div');
        leftContent.className = 'flex flex-wrap items-center gap-3 flex-1 min-w-0';

        // Type indicator with improved styling and better wrapping
        const typeIndicator = document.createElement('div');
        typeIndicator.className = `
            inline-flex items-center space-x-2 ${typeInfo.text} 
            px-2.5 py-1.5 rounded-full text-sm font-medium
            ${typeInfo.bg} border border-${typeInfo.border.split('-')[1]}
            break-normal
        `;
        typeIndicator.innerHTML = `
            <span class="flex-shrink-0">${typeInfo.icon}</span>
            <span class="font-medium truncate max-w-[200px]">${this.formatEventType(event.type || event.event)}</span>
        `;

        // Timestamp with improved layout
        const timestamp = document.createElement('div');
        timestamp.className = 'text-sm text-gray-500 flex items-center flex-shrink-0 whitespace-nowrap';
        timestamp.innerHTML = `
            <svg class="w-4 h-4 opacity-50 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
            </svg>
            <span>${new Date(event.timestamp || Date.now()).toLocaleTimeString()}</span>
        `;

        leftContent.appendChild(typeIndicator);
        leftContent.appendChild(timestamp);

        // Expand icon with improved positioning
        const expandIcon = document.createElement('div');
        expandIcon.className = 'flex-shrink-0 ml-auto';
        expandIcon.innerHTML = `
            <svg class="w-5 h-5 expand-icon transform transition-transform duration-200 text-gray-400">
                <path fill="currentColor" fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/>
            </svg>
        `;

        header.appendChild(leftContent);
        header.appendChild(expandIcon);

        return header;
    }

    createEventContentWrapper(event, typeInfo) {
        const wrapper = document.createElement('div');
        wrapper.className = 'hidden transition-all duration-300 ease-in-out';

        const content = document.createElement('div');
        content.className = 'p-4 border-t border-gray-200';

        // Add metadata section
        const metadata = document.createElement('div');
        metadata.className = 'flex items-center space-x-4 text-xs text-gray-500 mb-3';
        metadata.innerHTML = `
            <span class="flex items-center">
                <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
                </svg>
                ${new Date(event.timestamp || Date.now()).toLocaleString()}
            </span>
        `;
        content.appendChild(metadata);

        const inner = this.createEventContent(event.data || event);
        content.appendChild(inner);
        wrapper.appendChild(content);

        return wrapper;
    }

    createEventContent(data) {
        const content = document.createElement('div');
        content.className = 'space-y-3';

        if (!data) {
            const emptyState = document.createElement('div');
            emptyState.className = 'text-center py-4';
            emptyState.innerHTML = `
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <p class="mt-2 text-sm text-gray-500">No data available</p>
            `;
            content.appendChild(emptyState);
            return content;
        }

        if (typeof data === 'object') {
            Object.entries(data).forEach(([key, value]) => {
                if (value !== null && value !== undefined) {
                    const pair = this.createKeyValuePair(key, value);
                    content.appendChild(pair);
                }
            });
        } else {
            const valueWrapper = document.createElement('div');
            valueWrapper.className = 'prose prose-sm max-w-none';
            valueWrapper.innerHTML = this.formatValue(data);
            content.appendChild(valueWrapper);
        }

        // Add click handler for copy button if it exists
        const copyBtn = content.querySelector('.copy-prompt-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const promptText = data.current_prompt;
                navigator.clipboard.writeText(promptText).then(() => {
                    const originalText = copyBtn.innerHTML;
                    copyBtn.innerHTML = `<svg class="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>Copied!`;
                    copyBtn.classList.remove('text-gray-600', 'bg-gray-100', 'hover:bg-gray-200');
                    copyBtn.classList.add('text-green-600', 'bg-green-100');
                    setTimeout(() => {
                        copyBtn.innerHTML = originalText;
                        copyBtn.classList.remove('text-green-600', 'bg-green-100');
                        copyBtn.classList.add('text-gray-600', 'bg-gray-100', 'hover:bg-gray-200');
                    }, 2000);
                });
            });
        }

        return content;
    }

    createKeyValuePair(key, value) {
        const pair = document.createElement('div');
        pair.className = 'flex flex-wrap rounded-md p-3 hover:bg-gray-50/50 transition-colors duration-150 gap-2';

        const keyElement = document.createElement('div');
        keyElement.className = 'w-full sm:w-1/4 font-medium text-gray-700';
        keyElement.textContent = this.formatKey(key);

        const valueElement = document.createElement('div');
        valueElement.className = 'w-full sm:w-3/4 text-gray-900 break-words';
        valueElement.innerHTML = this.formatValue(value);

        pair.appendChild(keyElement);
        pair.appendChild(valueElement);

        return pair;
    }

    formatEventType(type) {
        if (!type) return 'Unknown Event';
        return type
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    formatKey(key) {
        if (!key) return '';
        return key
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    formatValue(value) {
        // Handle null or undefined values
        if (value === null || value === undefined) {
            return `<span class="text-gray-500 italic">null</span>`;
        }

        // Handle complex objects
        if (typeof value === 'object') {
            return this.formatComplexObject(value);
        }

        // Convert value to string to ensure consistent handling
        value = String(value);

        // Long text or multi-line content: use pre-formatted block with syntax highlighting
        if (value.includes('\n') || value.length > 100) {
            return `
                <div class="bg-gray-50 p-3 rounded-md border border-gray-200 overflow-x-auto">
                    <pre class="whitespace-pre-wrap break-words text-sm">
                        <code class="language-plaintext">${this.escapeHtml(value)}</code>
                    </pre>
                </div>
            `;
        }

        // Markdown content with code blocks or headers
        if (value.includes('```') || value.includes('#')) {
            // Use marked with advanced options for better rendering
            const markedOptions = {
                breaks: true,
                gfm: true,
                highlight: (code, lang) => {
                    try {
                        return hljs.highlightAuto(code, [lang]).value;
                    } catch {
                        return code;
                    }
                }
            };
            marked.setOptions(markedOptions);
            return `
                <div class="markdown-content bg-white p-2 rounded-md">
                    ${marked.parse(value)}
                </div>
            `;
        }

        // URL detection with improved styling
        if (value.match(/^https?:\/\/[^\s]+$/)) {
            return `
                <a href="${this.escapeHtml(value)}" 
                   target="_blank" 
                   rel="noopener noreferrer" 
                   class="text-blue-600 hover:text-blue-800 hover:underline flex items-center">
                    <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"></path>
                        <path d="M5 5a2 2 0 00-2 2v8a2 2 0 110 4v-3a1 1 0 10-2 0v3a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L5 9.586V7a1 1 0 00-2 0v5a1 1 0 001 1h5v-4a1 1 0 00-1-1H5z"></path>
                    </svg>
                    ${this.escapeHtml(value)}
                </a>
            `;
        }

        // Default text rendering with safe HTML escaping
        return `<span class="text-gray-800">${this.escapeHtml(value)}</span>`;
    }

    formatComplexObject(obj) {
        if (Array.isArray(obj)) {
            return `
                <div class="bg-gray-50 p-3 rounded-md border border-gray-200">
                    <div class="flex flex-wrap items-center justify-between mb-2 gap-2">
                        <span class="text-sm font-medium text-gray-500">Array</span>
                        <span class="text-xs bg-gray-200 px-2 py-1 rounded-full">${obj.length} items</span>
                    </div>
                    <div class="space-y-2 divide-y divide-gray-100">
                        ${obj.map((item, index) => `
                            <div class="flex flex-wrap items-start pt-2 first:pt-0 gap-2">
                                <span class="text-xs font-mono bg-gray-200 px-1.5 py-0.5 rounded shrink-0">${index}</span>
                                <div class="flex-1 min-w-0 break-words">${this.formatValue(item)}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        const entries = Object.entries(obj);
        if (entries.length === 0) {
            return '<span class="text-gray-500 italic">empty object</span>';
        }

        return `
            <div class="bg-gray-50 p-3 rounded-md border border-gray-200">
                <div class="flex flex-wrap items-center justify-between mb-2 gap-2">
                    <span class="text-sm font-medium text-gray-500">Object</span>
                    <span class="text-xs bg-gray-200 px-2 py-1 rounded-full">${entries.length} properties</span>
                </div>
                <div class="space-y-2 divide-y divide-gray-100">
                    ${entries.map(([key, val]) => `
                        <div class="flex flex-wrap items-start pt-2 first:pt-0 gap-2">
                            <span class="text-xs font-medium text-gray-700 font-mono bg-gray-200 px-1.5 py-0.5 rounded shrink-0">${this.escapeHtml(key)}</span>
                            <div class="flex-1 min-w-0 break-words">${this.formatValue(val)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}