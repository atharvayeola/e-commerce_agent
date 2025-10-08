"use client";

import { ChangeEvent, useCallback } from "react";

export default function ImageDropzone({ onUpload }: { onUpload: (file: File) => void }) {
  const handleChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        onUpload(file);
      }
    },
    [onUpload]
  );

  return (
    <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 hover:border-primary">
      <input type="file" accept="image/*" onChange={handleChange} className="hidden" />
      <span className="font-medium text-slate-700">Drop an image</span>
      <span className="text-xs text-slate-400">or click to upload and search visually</span>
    </label>
  );
}