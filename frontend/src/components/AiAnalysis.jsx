import React, { useState, useEffect } from 'react';
import { Bot, Sparkles, AlertTriangle, TrendingUp, TrendingDown, RefreshCcw, Brain, ChevronDown, ChevronUp } from 'lucide-react';
import { api, getPrompts } from '../services/api';
import ReactMarkdown from 'react-markdown';

// Parse markdown content and extract <think> blocks
const parseThinkBlocks = (markdown) => {
  if (!markdown) return [{ type: 'markdown', content: '' }];

  const blocks = [];
  const thinkRegex = /<think>([\s\S]*?)<\/think>/g;
  let lastIndex = 0;
  let match;

  while ((match = thinkRegex.exec(markdown)) !== null) {
    // Add markdown content before this think block
    if (match.index > lastIndex) {
      const markdownContent = markdown.slice(lastIndex, match.index).trim();
      if (markdownContent) {
        blocks.push({ type: 'markdown', content: markdownContent });
      }
    }

    // Add think block
    blocks.push({ type: 'think', content: match[1].trim() });
    lastIndex = thinkRegex.lastIndex;
  }

  // Add remaining markdown content
  if (lastIndex < markdown.length) {
    const markdownContent = markdown.slice(lastIndex).trim();
    if (markdownContent) {
      blocks.push({ type: 'markdown', content: markdownContent });
    }
  }

  return blocks.length > 0 ? blocks : [{ type: 'markdown', content: markdown }];
};

// ThinkBlock component with collapse/expand functionality
const ThinkBlock = ({ content }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="my-4 border border-slate-200 rounded-lg overflow-hidden bg-slate-50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2 text-slate-600">
          <Brain className="w-4 h-4" />
          <span className="text-sm font-medium">AI 思考过程</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 py-3 border-t border-slate-200 bg-white">
          <div className="prose prose-sm max-w-none text-slate-600 text-xs">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};


export const AiAnalysis = ({ fund }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [selectedPromptId, setSelectedPromptId] = useState(null);

  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    try {
      const data = await getPrompts();
      setPrompts(data);
      // Set default prompt as selected
      const defaultPrompt = data.find(p => p.is_default);
      if (defaultPrompt) {
        setSelectedPromptId(defaultPrompt.id);
      }
    } catch (error) {
      console.error('Load prompts failed', error);
    }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post('/ai/analyze_fund', {
        fund_info: fund,
        prompt_id: selectedPromptId
      });
      console.log('AI Analysis Response:', response.data);
      setAnalysis(response.data);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || '分析请求失败，请稍后重试';
      console.error('AI Analysis Error:', err);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (level) => {
    if (!level) return 'text-slate-500 bg-slate-100';
    if (level.includes('高')) return 'text-red-600 bg-red-50 border-red-100';
    if (level.includes('中')) return 'text-orange-600 bg-orange-50 border-orange-100';
    return 'text-green-600 bg-green-50 border-green-100';
  };

  // Extract risk level from markdown (look for ##  风险等级 section)
  const extractRiskLevel = (markdown) => {
    if (!markdown) return null;
    const match = markdown.match(/##\s*\s*风险等级\s*\n([^\n]+)/);
    return match ? match[1].trim() : null;
  };

  if (!analysis && !loading) {
    return (
      <div className="bg-gradient-to-br from-indigo-50 to-white rounded-2xl p-6 shadow-sm border border-indigo-100 flex flex-col items-center justify-center text-center">
        <Bot className="w-12 h-12 text-indigo-600 mb-3" />
        <h3 className="text-lg font-bold text-slate-800 mb-2">AI 深度市场分析</h3>
        <p className="text-slate-500 text-sm mb-6 max-w-md">
          基于 Linus Torvalds 风格的硬核逻辑分析。
          融合历史走势、实时估值、市场舆情，拒绝模棱两可的废话。
        </p>

        {/* Prompt Selector */}
        {prompts.length > 0 && (
          <div className="w-full max-w-md mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              选择分析风格
            </label>
            <select
              value={selectedPromptId || ''}
              onChange={(e) => setSelectedPromptId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
            >
              {prompts.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.is_default ? '(默认)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        <button
          onClick={handleAnalyze}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-full font-medium transition-all shadow-lg shadow-indigo-200 flex items-center gap-2"
        >
          <Sparkles className="w-4 h-4" /> 开始生成报告
        </button>
        {error && <p className="text-red-500 text-xs mt-4">{error}</p>}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 relative overflow-hidden">
      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
          <RefreshCcw className="w-8 h-8 text-indigo-600 animate-spin mb-3" />
          <p className="text-indigo-600 font-medium animate-pulse">Linus 正在审视市场逻辑...</p>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-start mb-6 border-b border-slate-50 pb-4">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-100 p-2 rounded-lg">
            <Bot className="w-6 h-6 text-indigo-700" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">AI 分析报告</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              生成时间: {analysis?.timestamp || '--:--'} ·
              <span className="ml-1 text-indigo-600 font-mono">Linus Mode</span>
            </p>
          </div>
        </div>

        {analysis?.indicators && (
            <div className="flex gap-2">
                {extractRiskLevel(analysis.markdown) && (
                  <span className={`px-2.5 py-1 rounded text-xs font-bold border ${getRiskColor(extractRiskLevel(analysis.markdown))}`}>
                      {extractRiskLevel(analysis.markdown)}
                  </span>
                )}
                <span className={`px-2.5 py-1 rounded text-xs font-bold border bg-slate-50 text-slate-600 border-slate-200`}>
                    位置: {analysis.indicators.status}
                </span>
            </div>
        )}
      </div>

      {/* Indicators Section */}
      {analysis?.indicators && (
        <div className="mb-6 bg-slate-50 rounded-xl p-4 text-xs text-slate-600 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-slate-400" />
            {analysis.indicators.desc}
        </div>
      )}

      {/* Main Content - Markdown with Think Block Support */}
      {analysis?.markdown ? (
        <div className="prose prose-sm max-w-none text-slate-700">
          {parseThinkBlocks(analysis.markdown).map((block, index) => {
            if (block.type === 'think') {
              return <ThinkBlock key={index} content={block.content} />;
            } else {
              return <ReactMarkdown key={index}>{block.content}</ReactMarkdown>;
            }
          })}
        </div>
      ) : analysis ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
          ⚠️ AI 返回数据格式错误：缺少 markdown 字段
          <pre className="mt-2 text-xs overflow-auto">{JSON.stringify(analysis, null, 2)}</pre>
        </div>
      ) : null}
      
      {!loading && analysis && (
        <div className="mt-6 flex justify-center">
            <button 
                onClick={handleAnalyze}
                className="text-slate-400 hover:text-indigo-600 text-xs flex items-center gap-1 transition-colors"
            >
                <RefreshCcw className="w-3 h-3" /> 重新分析
            </button>
        </div>
      )}
    </div>
  );
};
