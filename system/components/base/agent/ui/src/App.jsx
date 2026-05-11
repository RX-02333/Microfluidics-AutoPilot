import React from 'react';
import { ConfigProvider, theme, Avatar, Typography } from 'antd';
import { Bubble, Sender, Think, Prompts } from '@ant-design/x';
import { XStream } from "@ant-design/x-sdk"
import { UserOutlined, RobotOutlined, ExperimentOutlined, ToolOutlined } from '@ant-design/icons';
import XMarkdown from '@ant-design/x-markdown';
import Latex from '@ant-design/x-markdown/plugins/Latex';
import 'katex/dist/katex.min.css';
import './index.css';

const latexConfig = { extensions: Latex() };

// Think wrapper component
const ThinkWrapper = ({ content, title = "Thinking" }) => {
    const [expanded, setExpanded] = React.useState(false);

    return (
        <Think
            title={title}
            expanded={expanded}
            onExpand={(value) => setExpanded(value)}
        >
            <XMarkdown config={latexConfig}>{content}</XMarkdown>
        </Think>
    );
};

const App = ({ workflowPath: externalWorkflowPath }) => {
    const [content, setContent] = React.useState('');
    const [promptsVisible, setPromptsVisible] = React.useState(true);
    const [workflowPath, setWorkflowPath] = React.useState(externalWorkflowPath || null);

    // History-based state management
    const [history, setHistory] = React.useState([]);
    const [isStreaming, setIsStreaming] = React.useState(false);
    const [streamingMessage, setStreamingMessage] = React.useState(null);
    const listRef = React.useRef(null);
    const abortControllerRef = React.useRef(null);

    // Auto-scroll to bottom
    React.useEffect(() => {
        if (listRef.current) {
            setTimeout(() => {
                if (listRef.current) {
                    listRef.current.scrollTo({ top: 'bottom', behavior: 'smooth' });
                }
            }, 0);
        }
    }, [history, streamingMessage]);

    // Fetch workflow path
    React.useEffect(() => {
        if (!externalWorkflowPath) {
            fetch('/api/workflow_path')
                .then(response => response.json())
                .then(data => {
                    if (data.exists) {
                        setWorkflowPath(data.path);
                    }
                })
                .catch(error => console.error('Failed to fetch workflow path:', error));
        }
    }, [externalWorkflowPath]);

    // Ref to hold latest handleUserMessage to avoid stale closures in polling
    const handleUserMessageRef = React.useRef(null);

    // Poll for backend-pushed messages (e.g. interface detection, timer complete, troubleshooting)
    React.useEffect(() => {
        const interval = setInterval(async () => {
            // Don't process messages while streaming
            if (isStreaming) return;

            try {
                const response = await fetch('/ui/poll_messages');
                const data = await response.json();
                if (data.messages && data.messages.length > 0) {
                    for (const msg of data.messages) {
                        if (msg.type === 'user' && msg.content && handleUserMessageRef.current) {
                            // User-type: trigger Agent processing (like old system's send_notification_and_ai_process)
                            console.log('Auto-sending backend message to agent:', msg.content);
                            handleUserMessageRef.current(msg.content);
                            break; // Process one at a time
                        } else if (msg.type === 'system' && msg.content) {
                            // System-type: display only, not sent to Agent
                            console.log('System notification:', msg.content);
                            setHistory(prev => [...prev, { role: 'assistant', content: `📢 **System:** ${msg.content}`, _isNotification: true }]);
                        }
                    }
                }
            } catch (e) {
                // Silently ignore polling errors
            }
        }, 500);

        return () => clearInterval(interval);
    }, [isStreaming]);


    // Convert history (raw data) to messages (render data)
    // Merge consecutive assistant messages, use tags to format tool calls and results
    const convertHistoryToMessages = React.useCallback((hist, streaming = null) => {
        const messages = [];
        const workingHistory = streaming ? [...hist, streaming] : hist;

        let i = 0;
        while (i < workingHistory.length) {
            const msg = workingHistory[i];
            const { role, content, function_call, name } = msg;

            if (role === 'user') {
                // Process user message
                let displayContent = content;

                if (Array.isArray(content)) {
                    displayContent = content
                        .filter(item => item.text)
                        .map(item => item.text)
                        .join('\n');
                }

                messages.push({
                    key: `user-${i}`,
                    role: 'user',
                    content: displayContent || '',
                });
                i++;
            } else if (msg._isNotification) {
                // Notification messages: render as separate bubbles, never merge
                messages.push({
                    key: `notification-${i}`,
                    role: 'assistant',
                    content: msg.content || '',
                });
                i++;
            } else if (role === 'assistant' || role === 'function') {
                // Merge consecutive assistant and function messages (maintaining original order)
                let finalContent = '';
                let startIndex = i;
                const pendingToolCalls = {};  // id -> {name, arguments}

                // Process each message in order
                while (i < workingHistory.length && workingHistory[i].role !== 'user' && !workingHistory[i]._isNotification) {
                    const currentMsg = workingHistory[i];

                    if (currentMsg.role === 'assistant') {
                        // Process content (merge reasoning_content + filter empty think)
                        if (currentMsg.content || currentMsg.reasoning_content) {
                            // Build full content: reasoning (as <think>) + actual content
                            let rawContent = '';
                            if (currentMsg.reasoning_content) {
                                rawContent += `<think>${currentMsg.reasoning_content}</think>`;
                            }
                            rawContent += (currentMsg.content || '');
                            
                            let content = rawContent.replace(/<think>\s*<\/think>/g, '');
                            if (content.trim()) {
                                // Check for non-empty think
                                const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
                                if (thinkMatch && !thinkMatch[1].trim()) {
                                    content = content.replace(/<think>[\s\S]*?<\/think>/g, '');
                                }
                                if (content.trim()) {
                                    finalContent += content;
                                }
                            }
                        }

                        // Process function_call (record first, wait for result)
                        if (currentMsg.function_call) {
                            const id = currentMsg.extra?.function_id || 'default';
                            pendingToolCalls[id] = {
                                name: currentMsg.function_call.name,
                                arguments: currentMsg.function_call.arguments,
                            };
                        }
                    } else if (currentMsg.role === 'function') {
                        // Find corresponding tool call and output
                        const id = currentMsg.extra?.function_id || 'default';
                        const tc = pendingToolCalls[id];

                        if (tc) {
                            // Output tool_call
                            finalContent += `\n\n<tool_call>**Function:** ${tc.name}\n\n**Arguments:**\n${tc.arguments}</tool_call>`;
                            delete pendingToolCalls[id];
                        }

                        // Output tool_result
                        finalContent += `\n\n<tool_result name="${currentMsg.name}">${currentMsg.content}</tool_result>`;
                    }

                    i++;
                }

                // Process unmatched pending tool calls (might not have received result yet)
                for (const id in pendingToolCalls) {
                    const tc = pendingToolCalls[id];
                    finalContent += `\n\n<tool_call>**Function:** ${tc.name}\n\n**Arguments:**\n${tc.arguments}</tool_call>`;
                }

                messages.push({
                    key: `assistant-${startIndex}`,
                    role: 'assistant',
                    content: finalContent.trim(),
                });
            } else {
                // Skip unknown types
                i++;
            }
        }

        return messages;
    }, []);

    // Debug function: manually print history
    const debugPrintHistory = () => {
        console.log('=== History (raw data) ===');
        console.log(JSON.stringify(history, null, 2));
    };

    // Optimize history sent to backend
    // Group consecutive function call/assistant together, function result together
    const optimizeHistoryForBackend = (history) => {
        const optimized = [];
        let buffer = [];

        const flushBuffer = () => {
            if (buffer.length === 0) return;

            // Categorize messages
            const toolCalls = [];
            const toolResults = [];
            const normalAssistants = [];

            buffer.forEach(msg => {
                if (msg.role === 'assistant') {
                    if (msg.function_call) {
                        // Assistant message with function_call
                        toolCalls.push(msg);
                    } else {
                        // Normal assistant message (content / think)
                        normalAssistants.push(msg);
                    }
                } else if (msg.role === 'function') {
                    // Function result message
                    toolResults.push(msg);
                }
            });

            // Send order: 
            // 1. Tool Calls (assistant with function_call)
            // 2. Tool Results (function)
            // 3. Normal Output (assistant without function_call, e.g. Think or Final Answer)
            optimized.push(...toolCalls);
            optimized.push(...toolResults);
            optimized.push(...normalAssistants);

            buffer = [];
        };

        for (const msg of history) {
            // If assistant or function message, add to buffer
            if (msg.role === 'assistant' || msg.role === 'function') {
                buffer.push(msg);
            } else {
                // On user message or other, flush buffer first
                flushBuffer();
                optimized.push(msg);
            }
        }

        // Flush remaining buffer
        flushBuffer();

        return optimized;
    };

    // Stream processing function
    const handleUserMessage = React.useCallback(async (userInput) => {
        // Add user message to history
        // userInput can be string or array format [{'text': '...'}, {'file': '...'}]
        const newHistory = [...history, { role: 'user', content: userInput }];
        setHistory(newHistory);
        setIsStreaming(true);
        setContent('');


        // Filter out notification messages and strip frontend-only fields before sending to agent
        const historyForBackend = newHistory
            .filter(msg => !msg._isNotification)
            .map(({ reasoning_content, _isNotification, ...rest }) => rest);

        // Create AbortController
        abortControllerRef.current = new AbortController();

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ history: optimizeHistoryForBackend(historyForBackend) }),
                signal: abortControllerRef.current.signal,
            });

            let accumulatedHistory = [...newHistory];

            // Use XStream to process SSE
            for await (const chunk of XStream({
                readableStream: response.body,
            })) {
                // XStream return format: { data: "..." }
                const data = chunk.data || chunk;

                if (data === '[DONE]') {
                    // Stream ended
                    setHistory(accumulatedHistory);
                    setStreamingMessage(null);
                    break;
                }

                try {
                    // Parse JSON string
                    const msg = JSON.parse(data);

                    // Determine if updating existing message or adding new message
                    const lastMsg = accumulatedHistory[accumulatedHistory.length - 1];

                    let isSameMessage = false;

                    if (lastMsg && lastMsg.role === msg.role) {
                        if (msg.role === 'assistant') {
                            // Scenario 1: function_call streaming update (same tool call)
                            if (msg.function_call && lastMsg.function_call) {
                                // If it's the same tool (name and function_id are identical), it's a streaming update
                                const sameId = msg.extra?.function_id === lastMsg.extra?.function_id;
                                const sameName = msg.function_call.name === lastMsg.function_call.name;
                                isSameMessage = sameId && sameName;
                            }
                            // Scenario 2: Plain text content streaming update (neither has function_call)
                            else if (!msg.function_call && !lastMsg.function_call) {
                                isSameMessage = true;
                            }
                            // Scenario 3: From plain text to function_call, or switching from one tool to another, is a new message
                            else {
                                isSameMessage = false;
                            }
                        } else if (msg.role === 'function') {
                            // Scenario 4: Function result streaming update (same function_id)
                            const sameId = msg.extra?.function_id === lastMsg.extra?.function_id;
                            const sameName = msg.name === lastMsg.name;
                            isSameMessage = sameId && sameName;
                        }
                    }

                    // Preserve reasoning_content: if new msg lacks it but old msg had it, keep the old one
                    if (isSameMessage && lastMsg?.reasoning_content && !msg.reasoning_content) {
                        msg.reasoning_content = lastMsg.reasoning_content;
                    }

                    if (isSameMessage) {
                        // Update last message (streaming update)
                        accumulatedHistory[accumulatedHistory.length - 1] = msg;
                    } else {
                        // Add new message
                        accumulatedHistory.push(msg);
                    }

                    // Real-time update display
                    setStreamingMessage(msg);
                    setHistory([...accumulatedHistory]);
                } catch (e) {
                    console.error('Parse error:', e, 'data:', data);
                }
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Stream error:', error);
                // Add error message
                setHistory([...newHistory, {
                    role: 'assistant',
                    content: `Error: ${error.message}`,
                }]);
            }
        } finally {
            setIsStreaming(false);
            setStreamingMessage(null);
            abortControllerRef.current = null;
        }
    }, [history]);

    // Keep ref updated with latest handleUserMessage
    React.useEffect(() => {
        handleUserMessageRef.current = handleUserMessage;
    }, [handleUserMessage]);

    // Abort streaming
    const abort = React.useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setIsStreaming(false);
            setStreamingMessage(null);
        }
    }, []);

    // Convert to render items (messages array, adding streaming flag)
    const items = React.useMemo(() => {
        // history already contains the latest streaming message, no need to pass streamingMessage again
        const messages = convertHistoryToMessages(history, null);

        // If streaming, mark the last assistant message as streaming
        if (isStreaming && messages.length > 0) {
            const lastItem = messages[messages.length - 1];
            if (lastItem.role === 'assistant') {
                lastItem.streaming = true;
            }
        }

        console.log('Messages (render data):', JSON.stringify(messages, null, 2));

        return messages;
    }, [history, isStreaming, convertHistoryToMessages]);

    // Prompts configuration
    const promptItems = workflowPath ? [
        {
            key: 'start-experiment',
            icon: <ExperimentOutlined style={{ color: '#52C41A' }} />,
            label: 'Start Experiment',
            description: 'Begin the experimental workflow process',
        },
    ] : [];

    const handlePromptClick = (info) => {
        if (info.data.key === 'start-experiment' && workflowPath) {
            setPromptsVisible(false);
            // Send message with file path (array format)
            const absolutePath = workflowPath.startsWith('/') ? workflowPath.substring(1) : workflowPath;
            handleUserMessage([
                { text: 'start experiment' },
                { file: absolutePath }
            ]);
        }
    };

    // Role configuration - new rendering logic
    const role = React.useMemo(() => ({
        assistant: {
            placement: 'start',
            avatar: () => <Avatar icon={<RobotOutlined />} />,
            contentRender: (content) => {
                // Type guard: if content is not a string, render as-is
                if (typeof content !== 'string') {
                    return content;
                }
                // Parse tags in content and render
                const parts = [];
                let remaining = content;
                let key = 0;

                // Regex to match tags
                const thinkRegex = /<think>([\s\S]*?)<\/think>/g;
                const toolCallRegex = /<tool_call>([\s\S]*?)<\/tool_call>/g;
                const toolResultRegex = /<tool_result name="([^"]*)">([\s\S]*?)<\/tool_result>/g;

                // Replace tags with placeholders, record tag content
                const tags = [];

                // Extract <think>
                remaining = remaining.replace(thinkRegex, (match, thinkContent) => {
                    const placeholder = `__THINK_${tags.length}__`;
                    tags.push({ type: 'think', content: thinkContent });
                    return placeholder;
                });

                // Extract <tool_call>
                remaining = remaining.replace(toolCallRegex, (match, toolCallContent) => {
                    const placeholder = `__TOOLCALL_${tags.length}__`;
                    tags.push({ type: 'toolCall', content: toolCallContent });
                    return placeholder;
                });

                // Extract <tool_result>
                remaining = remaining.replace(toolResultRegex, (match, name, resultContent) => {
                    const placeholder = `__TOOLRESULT_${tags.length}__`;
                    tags.push({ type: 'toolResult', name, content: resultContent });
                    return placeholder;
                });

                // Split text and placeholders
                const segments = remaining.split(/(__(?:THINK|TOOLCALL|TOOLRESULT)_\d+__)/);

                for (const segment of segments) {
                    if (segment.match(/__THINK_(\d+)__/)) {
                        const index = parseInt(segment.match(/__THINK_(\d+)__/)[1]);
                        const tag = tags[index];
                        parts.push(
                            <ThinkWrapper key={key++} content={tag.content} title="Thinking" />
                        );
                    } else if (segment.match(/__TOOLCALL_(\d+)__/)) {
                        const index = parseInt(segment.match(/__TOOLCALL_(\d+)__/)[1]);
                        const tag = tags[index];
                        parts.push(
                            <ThinkWrapper key={key++} content={tag.content} title="Tool Call" />
                        );
                    } else if (segment.match(/__TOOLRESULT_(\d+)__/)) {
                        const index = parseInt(segment.match(/__TOOLRESULT_(\d+)__/)[1]);
                        const tag = tags[index];
                        parts.push(
                            <ThinkWrapper key={key++} content={tag.content} title={`Tool Result: ${tag.name}`} />
                        );
                    } else if (segment.trim()) {
                        parts.push(
                            <XMarkdown key={key++} config={latexConfig}>{segment}</XMarkdown>
                        );
                    }
                }

                return <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>{parts}</div>;
            },
        },
        user: {
            placement: 'end',
            avatar: () => <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />,
            contentRender: (content) => {
                return <XMarkdown config={latexConfig}>{content}</XMarkdown>;
            },
        },
    }), []);

    return (
        <ConfigProvider theme={{ algorithm: theme.defaultAlgorithm }}>
            <div className="agent-ui" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                {/* Chat Section */}
                <div className="chat-section" style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Message List */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column' }}>
                        <Bubble.List
                            ref={listRef}
                            style={{ flex: 1 }}
                            role={role}
                            items={items}
                            autoScroll={false}
                        />

                        {/* Prompts */}
                        {promptItems.length > 0 && promptsVisible && (
                            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 'auto', paddingTop: 20 }}>
                                <Prompts
                                    items={promptItems}
                                    onItemClick={handlePromptClick}
                                />
                            </div>
                        )}
                    </div>

                    {/* Input Box */}
                    <div style={{ padding: 20, borderTop: '1px solid #eee' }}>
                        <Sender
                            loading={isStreaming}
                            value={content}
                            onCancel={() => {
                                abort();
                            }}
                            onChange={setContent}
                            placeholder="Type a message and press Enter to send..."
                            onSubmit={(nextContent) => {
                                handleUserMessage(nextContent);
                                setPromptsVisible(false);
                            }}
                        />
                    </div>
                </div>
            </div>
        </ConfigProvider>
    );
};

export default App;
