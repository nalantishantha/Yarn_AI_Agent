import React, { useEffect, useState } from 'react';
import deleteIcon from '../assets/icons8-delete.svg';

export default function Sidebar({ currentThreadId, onSelectThread, onNewChat, refreshTrigger }) {
  const [sessions, setSessions] = useState([]);

  const fetchSessions = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/sessions');
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [currentThreadId, refreshTrigger]); 

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    try {
      await fetch(`http://localhost:8000/api/chat/sessions/${id}`, { method: 'DELETE' });
      if (id === currentThreadId) {
        onNewChat();
      } else {
        fetchSessions();
      }
    } catch (e) {
      console.error("Failed to delete", e);
    }
  };

  return (
    <div className="sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        + New Chat
      </button>
      <div className="sessions-list">
        {sessions.map(session => (
          <div 
            key={session.thread_id} 
            className={`session-item ${session.thread_id === currentThreadId ? 'active' : ''}`}
            onClick={() => onSelectThread(session.thread_id)}
          >
            <span className="session-title">{session.title}</span>
            <img 
              src={deleteIcon} 
              className="delete-btn" 
              onClick={(e) => handleDelete(e, session.thread_id)} 
              title="Delete chat" 
              alt="Delete" 
            />
          </div>
        ))}
      </div>
    </div>
  );
}
