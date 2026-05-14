import React, { useRef, useState } from "react";
import api from "../lib/api";
import { Button } from "./ui/button";
import { Upload, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function FileUploader({ kind = "doc", accept, onUploaded, label = "Téléverser un fichier", testid }) {
  const inputRef = useRef();
  const [loading, setLoading] = useState(false);

  const handle = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/upload?kind=${kind}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      onUploaded && onUploaded(data);
      toast.success("Fichier téléversé");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur d'upload");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div>
      <input ref={inputRef} type="file" accept={accept} onChange={handle} className="hidden" data-testid={`${testid}-input`} />
      <Button type="button" onClick={() => inputRef.current?.click()} variant="outline" className="rounded-full" disabled={loading} data-testid={testid}>
        {loading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />}
        {loading ? "Envoi..." : label}
      </Button>
    </div>
  );
}
