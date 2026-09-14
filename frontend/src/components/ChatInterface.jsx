import React, { useState, useRef, useEffect } from 'react';
import ChatMessage from './ChatMessage';

export default function ChatInterface({ threadId }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const endOfMessagesRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`http://localhost:8000/api/chat/sessions/${threadId}/messages`);
        const data = await res.json();
        setMessages(data.messages || []);
      } catch (error) {
        console.error('Failed to load history:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchHistory();
  }, [threadId]);

  const handleSend = async (messageText) => {
    const textToSend = messageText || inputValue;
    if (!textToSend.trim()) return;
    
    const userMessage = { text: textToSend, isUser: true };
    setMessages((prev) => [...prev, userMessage]);
    
    if (!messageText) setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.text,
          thread_id: threadId,
        }),
      });
      
      const data = await response.json();
      
      const agentMessage = {
        text: data.reply,
        isUser: false,
        isInterrupted: data.is_interrupted,
        pendingToolCall: data.pending_tool_call,
      };
      
      setMessages((prev) => [...prev, agentMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      setMessages((prev) => [...prev, { text: "Error connecting to the AI agent.", isUser: false }]);
    } finally {
      setIsLoading(false);
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleRejectPolicy = async () => {
    setIsLoading(true);
    setMessages((prev) => [...prev, { text: "No", isUser: true }]);
    try {
      const response = await fetch('http://localhost:8000/api/chat/reject-tool', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: "",
          thread_id: threadId,
        }),
      });
      
      const data = await response.json();
      setMessages((prev) => [...prev, { text: data.reply, isUser: false }]);
    } catch (error) {
      console.error('Failed to reject policy:', error);
      setMessages((prev) => [...prev, { text: "Error connecting to the AI agent.", isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprovePolicy = async () => {
    setIsLoading(true);
    setMessages((prev) => [...prev, { text: "Yes, Approve", isUser: true }]);
    try {
      const response = await fetch('http://localhost:8000/api/chat/approve-tool', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: "",
          thread_id: threadId,
        }),
      });
      
      const data = await response.json();
      setMessages((prev) => [...prev, { text: data.reply, isUser: false }]);
    } catch (error) {
      console.error('Failed to approve policy:', error);
      setMessages((prev) => [...prev, { text: "Error connecting to the AI agent.", isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e) => {
    setInputValue(e.target.value);
    // Auto-resize textarea
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Yarn Selection AI Agent</h2>
      </div>
      
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="empty-state">
            <h3>Welcome to Yarn AI!</h3>
            <p>I can help you select, filter, and score yarns across multiple requirements.</p>
            
            <div className="prompt-guide">
              <h4>How to write a perfect search prompt:</h4>
              <p>
                To get the best results for an order, state your requirements clearly:
                <br /><br />
                • <strong>Multi-Yarn Selection:</strong> List each yarn separately (e.g., Yarn 1, Yarn 2) with its required material and hard limits (like "under $10").<br />
                • <strong>Priorities:</strong> Tell me what matters most for each yarn. You can use exact percentages (e.g., "100% price") or just general preferences (e.g., "prioritize lead time"), and I will help you balance them.<br />
                • <strong>Situational Policies:</strong> If you need to exclude a supplier just for this order, or create a long-term rule (e.g., "always exclude Toray"), include that directly in your request.
              </p>
              
              <div className="example-block">
                <strong>Example Prompt:</strong>
                <p>
                  "I need an article with 3 yarns.<br/>
                  Yarn 1: Cotton under $10, prioritize price 100%.<br/>
                  Yarn 2: Elastane, I want to prioritize lead time but give me some options.<br/>
                  Yarn 3: Polyester, 100% quality. Also, exclude supplier Toray for this entire order."
                </p>
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <React.Fragment key={index}>
              <ChatMessage message={msg.text} isUser={msg.isUser} />
              
              {/* Show approval buttons if the agent is waiting for confirmation */}
              {msg.isInterrupted && index === messages.length - 1 && (
                <div className="policy-approval-buttons">
                  <button className="btn-approve" onClick={handleApprovePolicy} disabled={isLoading}>
                    Yes, Approve
                  </button>
                  <button className="btn-reject" onClick={handleRejectPolicy} disabled={isLoading}>
                    No, Reject
                  </button>
                </div>
              )}
            </React.Fragment>
          ))
        )}
        {isLoading && (
          <div className="message-wrapper agent-message">
            <div className="message-avatar">AI</div>
            <div className="message-content typing-indicator">
              <span>●</span><span>●</span><span>●</span>
            </div>
          </div>
        )}
        <div ref={endOfMessagesRef} className="scroll-anchor" />
      </div>

      <div className="chat-input-area">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInput}
            onKeyDown={handleKeyPress}
            placeholder="Type your message here..."
            rows="1"
          />
          <button className="send-btn" onClick={() => handleSend()} disabled={isLoading || !inputValue.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
