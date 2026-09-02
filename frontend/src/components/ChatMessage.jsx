import React from 'react';
import ReactMarkdown from 'react-markdown';

export default function ChatMessage({ message, isUser }) {
  return (
    <div className={`message-wrapper ${isUser ? 'user-message' : 'agent-message'}`}>
      <div className="message-avatar">
        {isUser ? 'U' : 'AI'}
      </div>
      <div className="message-content">
        {isUser ? (
          <p>{message}</p>
        ) : (
          <ReactMarkdown>{message}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
