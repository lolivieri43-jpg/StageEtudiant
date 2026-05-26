import React, { useState } from "react";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Type, Heading1, Image as ImageIcon, Award, MousePointer, Tag, Link as LinkIcon, GripVertical, Trash2, Plus } from "lucide-react";

const BLOCK_DEFS = [
  { type: "heading",    label: "Titre",     icon: Heading1,     defaults: { content: "Mon super titre", style: { font_size: 22, font_weight: 800 } } },
  { type: "text",       label: "Texte",     icon: Type,         defaults: { content: "Ajoutez ici votre texte descriptif.", style: { font_size: 14 } } },
  { type: "image",      label: "Image",     icon: ImageIcon,    defaults: { image_url: "", content: "Description de l'image", style: {} } },
  { type: "logo",       label: "Logo",      icon: Award,        defaults: { image_url: "", style: { size: 64 } } },
  { type: "button",     label: "Bouton",    icon: MousePointer, defaults: { content: "Découvrir", url: "https://", style: {} } },
  { type: "promo_code", label: "Code promo",icon: Tag,          defaults: { content: "PROMO20", style: {} } },
  { type: "link",       label: "Lien",      icon: LinkIcon,     defaults: { content: "Cliquez ici", url: "https://", style: {} } },
];

const newId = () => `b_${Math.random().toString(36).slice(2, 10)}`;

export default function AdBuilder({ blocks, onChange, accentColor = "#2563eb" }) {
  const [selected, setSelected] = useState(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const addBlock = (def) => {
    const block = { id: newId(), type: def.type, order: blocks.length, ...def.defaults };
    onChange([...blocks, block]);
    setSelected(block.id);
  };

  const updateBlock = (id, patch) => {
    onChange(blocks.map(b => b.id === id ? { ...b, ...patch, style: { ...b.style, ...(patch.style || {}) } } : b));
  };

  const removeBlock = (id) => {
    onChange(blocks.filter(b => b.id !== id));
    if (selected === id) setSelected(null);
  };

  const onDragEnd = (e) => {
    const { active, over } = e;
    if (over && active.id !== over.id) {
      const oldIndex = blocks.findIndex(b => b.id === active.id);
      const newIndex = blocks.findIndex(b => b.id === over.id);
      onChange(arrayMove(blocks, oldIndex, newIndex).map((b, i) => ({ ...b, order: i })));
    }
  };

  const sel = blocks.find(b => b.id === selected);

  return (
    <div className="grid grid-cols-12 gap-4" data-testid="ad-builder">
      {/* Palette */}
      <div className="col-span-12 sm:col-span-3 space-y-2" data-testid="builder-palette">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Blocs</div>
        {BLOCK_DEFS.map(d => (
          <button key={d.type} type="button" onClick={() => addBlock(d)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 hover:border-violet-300 hover:bg-violet-50 text-sm"
                  data-testid={`add-block-${d.type}`}>
            <d.icon className="w-4 h-4 text-violet-600" />
            <span className="font-semibold">{d.label}</span>
            <Plus className="w-3 h-3 ml-auto text-slate-400" />
          </button>
        ))}
      </div>

      {/* Canvas */}
      <div className="col-span-12 sm:col-span-6">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Composition (glissez pour réordonner)</div>
        <div className="rounded-2xl border-2 border-dashed border-slate-200 p-3 min-h-[300px] space-y-2 bg-slate-50" data-testid="builder-canvas">
          {blocks.length === 0 && (
            <div className="text-center text-sm text-slate-400 py-10">
              Ajoutez des blocs depuis la palette de gauche.
            </div>
          )}
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={blocks.map(b => b.id)} strategy={verticalListSortingStrategy}>
              {blocks.map(b => (
                <SortableBlockRow key={b.id} block={b}
                                  selected={selected === b.id}
                                  onSelect={() => setSelected(b.id)}
                                  onRemove={() => removeBlock(b.id)} />
              ))}
            </SortableContext>
          </DndContext>
        </div>
      </div>

      {/* Properties */}
      <div className="col-span-12 sm:col-span-3">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Propriétés</div>
        {!sel && (
          <div className="text-xs text-slate-400 italic">Sélectionnez un bloc pour modifier ses propriétés</div>
        )}
        {sel && <BlockProperties block={sel} onUpdate={(p) => updateBlock(sel.id, p)} accentColor={accentColor} />}
      </div>
    </div>
  );
}

function SortableBlockRow({ block, selected, onSelect, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };
  return (
    <div ref={setNodeRef} style={style}
         onClick={onSelect}
         className={`bg-white rounded-xl border ${selected ? "border-violet-500 ring-2 ring-violet-100" : "border-slate-200"} px-3 py-2 flex items-center gap-2 cursor-pointer`}
         data-testid={`block-${block.id}`}>
      <button {...attributes} {...listeners} className="cursor-grab text-slate-400 hover:text-slate-600 touch-none" title="Glisser">
        <GripVertical className="w-4 h-4" />
      </button>
      <BlockPreviewInline block={block} />
      <button onClick={(e) => { e.stopPropagation(); onRemove(); }} className="text-slate-400 hover:text-rose-600 p-1" title="Supprimer" data-testid={`remove-block-${block.id}`}>
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function BlockPreviewInline({ block }) {
  const def = BLOCK_DEFS.find(d => d.type === block.type);
  const Icon = def?.icon || Type;
  return (
    <div className="flex-1 min-w-0 flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-violet-600 font-bold flex items-center gap-1">
        <Icon className="w-3 h-3" />{def?.label || block.type}
      </span>
      <span className="text-sm text-slate-700 truncate">
        {block.type === "image" || block.type === "logo"
          ? (block.image_url || "(URL d'image vide)")
          : (block.content || "—")}
      </span>
    </div>
  );
}

function BlockProperties({ block, onUpdate, accentColor }) {
  const isVisual = ["image", "logo"].includes(block.type);
  const hasUrl = ["button", "link", "image"].includes(block.type);
  return (
    <div className="space-y-3 text-sm">
      {!isVisual && (
        <div>
          <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">Contenu</label>
          <textarea value={block.content || ""} onChange={(e) => onUpdate({ content: e.target.value })}
                    rows={3} className="w-full rounded-xl border border-slate-200 p-2 mt-1 text-sm" data-testid="prop-content" />
        </div>
      )}
      {isVisual && (
        <div>
          <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">URL image</label>
          <input value={block.image_url || ""} onChange={(e) => onUpdate({ image_url: e.target.value })}
                 placeholder="https://..."
                 className="w-full rounded-xl border border-slate-200 h-9 px-2 mt-1 text-sm" data-testid="prop-image-url" />
        </div>
      )}
      {hasUrl && (
        <div>
          <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">URL cible</label>
          <input value={block.url || ""} onChange={(e) => onUpdate({ url: e.target.value })}
                 placeholder="https://..."
                 className="w-full rounded-xl border border-slate-200 h-9 px-2 mt-1 text-sm" data-testid="prop-url" />
        </div>
      )}
      {(block.type === "heading" || block.type === "text") && (
        <>
          <div>
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">Taille texte</label>
            <input type="range" min="10" max="36" value={block.style?.font_size || 14}
                   onChange={(e) => onUpdate({ style: { font_size: Number(e.target.value) } })}
                   className="w-full" data-testid="prop-font-size" />
            <div className="text-[11px] text-slate-500">{block.style?.font_size || 14}px</div>
          </div>
          <div>
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">Alignement</label>
            <div className="flex gap-1 mt-1">
              {["left","center","right"].map(a => (
                <button key={a} type="button" onClick={() => onUpdate({ style: { text_align: a } })}
                        className={`flex-1 h-8 rounded-lg text-xs font-bold ${block.style?.text_align === a ? "bg-slate-900 text-white" : "bg-slate-100"}`}
                        data-testid={`prop-align-${a}`}>{a === "left" ? "G" : a === "center" ? "C" : "D"}</button>
              ))}
            </div>
          </div>
        </>
      )}
      <div>
        <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">Couleur texte</label>
        <input type="color" value={block.style?.color || "#0f172a"} onChange={(e) => onUpdate({ style: { color: e.target.value } })}
               className="w-full h-9 rounded-xl mt-1" data-testid="prop-color" />
      </div>
      {block.type === "button" && (
        <div>
          <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">Fond bouton</label>
          <input type="color" value={block.style?.bg_color || accentColor} onChange={(e) => onUpdate({ style: { bg_color: e.target.value } })}
                 className="w-full h-9 rounded-xl mt-1" data-testid="prop-bg-color" />
        </div>
      )}
    </div>
  );
}

// Renderer used in previews (NewAdPage preview pane + DealsPage SponsoredAdCard)
export function RenderBlocks({ blocks, accentColor = "#2563eb" }) {
  const sorted = [...(blocks || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  return (
    <div className="space-y-2 px-4 py-4">
      {sorted.map(b => <RenderBlock key={b.id} block={b} accentColor={accentColor} />)}
    </div>
  );
}

function RenderBlock({ block, accentColor }) {
  const st = block.style || {};
  const common = {
    color: st.color,
    textAlign: st.text_align,
  };
  switch (block.type) {
    case "heading":
      return <div style={{ ...common, fontSize: (st.font_size || 22), fontWeight: st.font_weight || 800 }}>{block.content}</div>;
    case "text":
      return <div style={{ ...common, fontSize: (st.font_size || 14) }}>{block.content}</div>;
    case "image":
      return block.image_url ? <img src={block.image_url} alt="" className="w-full rounded-lg max-h-64 object-cover" /> : null;
    case "logo":
      return block.image_url ? (
        <div className="flex" style={{ justifyContent: st.text_align === "center" ? "center" : st.text_align === "right" ? "flex-end" : "flex-start" }}>
          <img src={block.image_url} alt="" style={{ width: (st.size || 64), height: (st.size || 64) }} className="rounded-lg object-cover" />
        </div>
      ) : null;
    case "button":
      return (
        <div style={{ textAlign: st.text_align || "center" }}>
          <span className="inline-block text-sm font-bold py-2 px-4 rounded-xl"
                style={{ background: st.bg_color || accentColor, color: st.color || "#fff" }}>
            {block.content || "Bouton"}
          </span>
        </div>
      );
    case "promo_code":
      return (
        <div style={{ textAlign: st.text_align || "center" }}>
          <span className="inline-block text-xs font-bold border border-dashed px-3 py-1.5 rounded-lg font-mono"
                style={{ borderColor: accentColor, color: st.color || accentColor }}>
            {block.content || "CODE"}
          </span>
        </div>
      );
    case "link":
      return (
        <a href={block.url || "#"} target="_blank" rel="noreferrer"
           className="text-sm underline" style={{ color: st.color || accentColor }}>
          {block.content || block.url}
        </a>
      );
    default:
      return null;
  }
}
