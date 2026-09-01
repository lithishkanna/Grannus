'use client';
import { useState, useRef, ChangeEvent, DragEvent } from 'react';
import { Upload, FileAudio, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { motion } from 'framer-motion';

export function FileUploader({ onAudioReady }: { onAudioReady: (blob: Blob) => void }) {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = (f: File) => {
    if (f.type.startsWith('audio/')) {
      setFile(f);
      const url = URL.createObjectURL(f);
      setAudioUrl(url);
      onAudioReady(f);
    } else {
      alert('Please upload a valid audio file.');
    }
  };

  const handleRemove = () => {
    setFile(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 bg-card rounded-organic-3 shadow-ink-wash border border-border gap-6 w-full h-full min-h-[350px]">
      {!file ? (
        <div 
          className={`flex flex-col items-center justify-center w-full h-full border-2 border-dashed rounded-xl p-8 transition-colors ${isDragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 cursor-pointer'}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input 
            type="file" 
            ref={fileInputRef} 
            className="hidden" 
            accept="audio/*" 
            onChange={handleChange} 
          />
          <motion.div whileHover={{ y: -5 }}>
            <Upload className="w-12 h-12 text-muted-foreground mb-4" />
          </motion.div>
          <h3 className="font-heading text-lg font-medium text-foreground mb-2">Upload Audio File</h3>
          <p className="text-sm text-muted-foreground text-center mb-6 max-w-xs">
            Drag and drop an audio file here, or click to browse.
          </p>
          <div className="text-xs text-muted-foreground/70 flex gap-2">
            <span>MP3</span> • <span>WAV</span> • <span>WEBM</span> • <span>OGG</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-6 w-full max-w-sm animate-gentle-fade-in">
          <div className="w-20 h-20 bg-primary/10 rounded-organic-2 flex items-center justify-center text-primary mb-2">
            <FileAudio className="w-10 h-10" />
          </div>
          
          <div className="text-center">
            <p className="font-medium text-foreground truncate max-w-[250px]">{file.name}</p>
            <p className="text-sm text-muted-foreground mt-1">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
          </div>

          <div className="w-full bg-background rounded-full px-4 py-2 border border-border shadow-inner">
             <audio src={audioUrl!} controls className="w-full h-10" />
          </div>
          
          <Button variant="outline" onClick={handleRemove} className="gap-2 rounded-full px-6 text-destructive hover:text-destructive hover:bg-destructive/10">
            <X className="w-4 h-4" />
            Remove File
          </Button>
        </div>
      )}
    </div>
  );
}
