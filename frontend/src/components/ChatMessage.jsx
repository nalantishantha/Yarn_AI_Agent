import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Custom renderers for ReactMarkdown
const markdownComponents = {
  // Wrap tables in a scrollable container so wide tables don't overflow the chat bubble
  table: ({ node, ...props }) => (
    <div className="table-wrapper">
      <table {...props} />
    </div>
  ),
};

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
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}

