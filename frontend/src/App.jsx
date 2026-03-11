import React, { useState, useRef } from 'react';
import { UploadCloud, FileType, CheckCircle, FileText, Download, Loader2, X, ArrowRight, Settings2 } from 'lucide-react';

export default function App() {
    const [files, setFiles] = useState([]);
    const [isUploading, setIsUploading] = useState(false);
    const [results, setResults] = useState(null);
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = useRef(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const pdfFiles = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
            setFiles(prev => [...prev, ...pdfFiles]);
        }
    };

    const handleSelectFiles = (e) => {
        if (e.target.files && e.target.files[0]) {
            const pdfFiles = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
            setFiles(prev => [...prev, ...pdfFiles]);
        }
    };

    const removeFile = (index) => {
        setFiles(files.filter((_, i) => i !== index));
    };

    const processFiles = async () => {
        if (files.length === 0) return;
        setIsUploading(true);

        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        try {
            const res = await fetch('http://localhost:8000/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) throw new Error('Ошибка обработки');

            const data = await res.json();
            setResults(data);
        } catch (err) {
            alert("Произошла ошибка при загрузке и обработке файлов. Проверьте, запущен ли backend сервер.");
            console.error(err);
        } finally {
            setIsUploading(false);
        }
    };

    const downloadFile = (content, filename, type) => {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const exportJSON = () => {
        if (!results) return;
        downloadFile(JSON.stringify(results.data, null, 2), "rag_converted.json", "application/json");
    };

    const exportMarkdown = () => {
        if (!results) return;
        let md = "# PDF to RAG - Результаты конвертации\n\n";
        results.data.forEach(chunk => {
            md += `### [${chunk.source}] Раздел: ${chunk.section} (Стр. ${chunk.page})\n`;
            md += `**Теги:** ${chunk.tags?.join(', ') || 'нет'}\n\n`;
            md += `${chunk.text}\n\n---\n\n`;
        });
        downloadFile(md, "rag_converted.md", "text/markdown");
    };

    const exportTXT = () => {
        if (!results) return;
        let txt = "";
        results.data.forEach(chunk => {
            txt += `SOURCE: ${chunk.source} | SECTION: ${chunk.section} | PAGE: ${chunk.page}\n`;
            txt += `TAGS: ${chunk.tags?.join(', ') || 'нет'}\n\n`;
            txt += `${chunk.text}\n\n`;
            txt += `=========================================================================\n\n`;
        });
        downloadFile(txt, "rag_converted.txt", "text/plain");
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-6 sm:p-12 overflow-x-hidden">
            {/* Background Decor */}
            <div className="fixed top-0 left-0 w-full h-full -z-10 overflow-hidden pointer-events-none">
                <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-100 rounded-full blur-[100px] opacity-50"></div>
                <div className="absolute bottom-[-10%] left-[-10%] w-[30%] h-[30%] bg-indigo-100 rounded-full blur-[100px] opacity-50"></div>
            </div>

            <div className="max-w-4xl w-full animate-fade-in">
                <header className="flex flex-col items-center mb-12">
                    <div className="mb-6 hover:scale-105 transition-transform duration-300">
                        <img src="/logo.svg" alt="Logo" className="h-16 w-auto" onError={(e) => e.target.style.display = 'none'} />
                        <div className="hidden only:block bg-blue-700 text-white p-4 rounded-2xl shadow-xl">
                            <FileType size={32} />
                        </div>
                    </div>
                    <h1 className="text-5xl font-bold text-gray-900 tracking-tight mb-3 text-center">Converter PDF</h1>
                    <p className="text-xl text-gray-600 font-medium text-center">Конвертация базы знаний в структурированный RAG формат</p>
                </header>

                <div className="glass-card rounded-[2rem] p-10 relative overflow-hidden">
                    {!results ? (
                        <div className="space-y-8">
                            {/* Step 1: Upload */}
                            <div
                                className={`relative group border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 
                  ${dragActive ? "border-blue-600 bg-blue-50/50 scale-[0.99]" : "border-gray-200 hover:border-blue-400 hover:bg-white/50"}`}
                                onDragEnter={handleDrag}
                                onDragLeave={handleDrag}
                                onDragOver={handleDrag}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <input
                                    type="file"
                                    multiple
                                    accept=".pdf"
                                    className="hidden"
                                    ref={fileInputRef}
                                    onChange={handleSelectFiles}
                                />

                                <div className="mb-6 relative inline-block">
                                    <div className="absolute inset-0 bg-blue-500 rounded-full blur-2xl opacity-20 animate-pulse"></div>
                                    <UploadCloud className="w-20 h-20 text-blue-600 relative z-10 mx-auto" strokeWidth={1.5} />
                                </div>

                                <h3 className="text-2xl font-bold text-gray-900 mb-2">Загрузите ваши PDF документы</h3>
                                <p className="text-gray-500 text-lg mb-8">просто перетащите файлы сюда</p>

                                <div className="flex justify-center">
                                    <span className="btn-primary">
                                        <Settings2 size={20} /> Выбрать файлы
                                    </span>
                                </div>
                            </div>

                            {files.length > 0 && (
                                <div className="space-y-4 animate-fade-in">
                                    <div className="flex justify-between items-end">
                                        <h4 className="text-lg font-bold text-gray-800">
                                            Выбрано для обработки <span className="text-blue-600">({files.length})</span>
                                        </h4>
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                                        {files.map((file, i) => (
                                            <div key={i} className="flex items-center justify-between p-4 bg-white/80 border border-gray-100 rounded-xl shadow-sm group">
                                                <div className="flex items-center gap-3 overflow-hidden">
                                                    <FileType className="shrink-0 w-8 h-8 text-red-500" />
                                                    <span className="font-semibold text-gray-700 truncate">{file.name}</span>
                                                </div>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                                                    className="p-1 hover:bg-red-50 rounded-full text-red-400 hover:text-red-600 transition-colors"
                                                >
                                                    <X size={20} />
                                                </button>
                                            </div>
                                        ))}
                                    </div>

                                    <button
                                        onClick={processFiles}
                                        disabled={isUploading}
                                        className="btn-primary w-full text-lg py-4 shadow-blue-200 shadow-xl mt-4"
                                    >
                                        {isUploading ? (
                                            <>
                                                <Loader2 className="w-6 h-6 animate-spin" />
                                                Обработка...
                                            </>
                                        ) : (
                                            <>
                                                <ArrowRight className="w-6 h-6" />
                                                Загрузить и начать конвертацию
                                            </>
                                        )}
                                    </button>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="animate-fade-in space-y-8 text-center sm:text-left">
                            <div className="text-center">
                                <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 text-green-600 rounded-full mb-6">
                                    <CheckCircle size={40} strokeWidth={2.5} />
                                </div>
                                <h2 className="text-3xl font-bold text-gray-900 mb-2">Готово!</h2>
                                <p className="text-gray-600 text-lg">
                                    Мы подготовили <span className="font-bold text-blue-600">{results.data?.length || 0}</span> фрагментов.
                                </p>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <button
                                    onClick={exportJSON}
                                    className="btn-primary h-16"
                                >
                                    <Download className="w-5 h-5" />
                                    JSON
                                </button>

                                <button
                                    onClick={exportMarkdown}
                                    className="btn-secondary h-16 border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                                >
                                    <FileText className="w-5 h-5" />
                                    Markdown
                                </button>

                                <button
                                    onClick={exportTXT}
                                    className="btn-secondary h-16"
                                >
                                    <FileText className="w-5 h-5" />
                                    TXT
                                </button>
                            </div>

                            <div className="pt-8 border-t border-gray-100">
                                <div className="flex justify-between items-center mb-6">
                                    <h4 className="font-bold text-xl text-gray-800 font-ubuntu">Предпросмотр данных</h4>
                                    <button
                                        onClick={() => { setResults(null); setFiles([]); }}
                                        className="text-blue-600 font-bold hover:text-blue-800 transition-colors flex items-center gap-1"
                                    >
                                        Сбросить
                                    </button>
                                </div>

                                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-4 custom-scrollbar text-left">
                                    {results.data?.slice(0, 5).map((chunk, idx) => (
                                        <div key={idx} className="p-6 bg-white/40 border border-white rounded-2xl shadow-sm hover:shadow-md transition-shadow">
                                            <div className="flex flex-wrap items-center gap-2 mb-4">
                                                <span className="bg-blue-600 text-white text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-wider">
                                                    {chunk.section}
                                                </span>
                                                <span className="bg-gray-200 text-gray-700 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                                                    PAGE {chunk.page}
                                                </span>
                                                {chunk.tags?.map(tag => (
                                                    <span key={tag} className="border border-blue-200 text-blue-700 text-[10px] font-bold px-3 py-1 rounded-full uppercase">
                                                        #{tag}
                                                    </span>
                                                ))}
                                            </div>
                                            <p className="text-gray-800 leading-relaxed text-sm italic">
                                                "{chunk.text.substring(0, 300)}..."
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <footer className="mt-12 text-center text-gray-400 font-medium">
                    <p>&copy; 2024 AI Knowledge Base Processor.</p>
                </footer>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #cbd5e1; }
      `}} />
        </div>
    );
}
