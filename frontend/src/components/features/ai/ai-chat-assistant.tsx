'use client';

import React, { useState } from 'react';
import { Sparkles, X } from 'lucide-react';

export function AIChatAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<{ sender: 'user' | 'ai'; text: string }[]>([]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { sender: 'user', text: input }]);
    // AI call logic
    setInput('');
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {!isOpen ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          title="AI Sales Assistant"
          aria-label="Open AI Sales Assistant"
          className="bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white rounded-full w-12 h-12 sm:w-14 sm:h-14 shadow-lg flex items-center justify-center transition cursor-pointer"
        >
          <Sparkles className="w-6 h-6" />
        </button>
      ) : (
        <div className="w-[calc(100vw-3rem)] max-w-80 sm:w-80 h-96 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl flex flex-col p-4">
          <div className="flex justify-between items-center pb-2 border-b border-gray-800">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>AI Sales Assistant</span>
            </h3>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white cursor-pointer transition p-1"
              aria-label="Close AI Sales Assistant"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto my-2 space-y-2 text-sm text-gray-300">
            {messages.length === 0 && (
              <p className="text-gray-500 italic text-center mt-10">How can I assist your sales team today?</p>
            )}
            {messages.map((m, idx) => (
              <div key={idx} className={`p-2 rounded ${m.sender === 'user' ? 'bg-indigo-600 text-white self-end' : 'bg-gray-800 text-gray-200'}`}>
                {m.text}
              </div>
            ))}
          </div>
          <div className="flex gap-2 pt-2 border-t border-gray-800">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask AI..."
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm text-white focus:outline-none"
            />
            <button
              type="button"
              onClick={handleSend}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded text-sm cursor-pointer"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
