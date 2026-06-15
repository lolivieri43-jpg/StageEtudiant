import React from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../ui/dialog";
import SiretLookup from "../SiretLookup";
import { DIPLOMA_LEVELS } from "../../lib/diplomas";

const Field = ({ label, value, onChange, testid }) => (
  <div>
    <Label>{label}</Label>
    <Input value={value || ""} onChange={(e) => onChange(e.target.value)} className="rounded-xl mt-1" data-testid={testid} />
  </div>
);

/**
 * Modal form to edit a profile (company or candidate). Owned state lives in
 * the parent (`form`, `setForm`) so the dialog stays controlled.
 */
export default function ProfileEditDialog({ open, onOpenChange, isCompany, form, setForm, onSave }) {
  const setKey = (k, v) => setForm({ ...form, [k]: v });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Modifier mon profil</DialogTitle>
          <DialogDescription className="sr-only">
            Mettez à jour les informations affichées sur votre profil public.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {isCompany ? (
            <>
              <div className="bg-blue-50 border border-blue-100 rounded-2xl p-3">
                <Label className="text-blue-900 font-semibold text-xs">Rechercher dans l&apos;Annuaire officiel</Label>
                <p className="text-[11px] text-slate-600 mb-2">Préremplit nom, SIRET, adresse, NAF...</p>
                <SiretLookup
                  onSelect={(c) => setForm({
                    ...form,
                    company_name: c.name || form.company_name,
                    siret: c.siret || form.siret,
                    siren: c.siren,
                    city: c.city || form.city,
                    postal_code: c.postal_code,
                    region: c.region || form.region,
                    address: c.address || form.address,
                    naf_code: c.naf_code,
                    siret_verified: true,
                    siret_verified_at: new Date().toISOString(),
                  })}
                  defaultQuery={form.company_name}
                />
              </div>
              <Field label="Nom de l'entreprise" value={form.company_name} onChange={(v) => setKey("company_name", v)} testid="edit-company-name" />
              <Field label="SIRET" value={form.siret} onChange={(v) => setKey("siret", v)} testid="edit-siret" />
              <Field label="Secteur" value={form.sector} onChange={(v) => setKey("sector", v)} testid="edit-sector" />
              <Field label="Taille" value={form.size} onChange={(v) => setKey("size", v)} />
              <Field label="Ville" value={form.city} onChange={(v) => setKey("city", v)} />
              <Field label="Site web" value={form.website} onChange={(v) => setKey("website", v)} />
              <Field label="Logo URL" value={form.logo} onChange={(v) => setKey("logo", v)} />
              <div>
                <Label>Statut de recrutement</Label>
                <select value={form.company_status || "recrute_les_deux"} onChange={(e) => setKey("company_status", e.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="edit-company-status">
                  <option value="recrute_stagiaire">Recherche stagiaire</option>
                  <option value="recrute_alternant">Recherche alternant</option>
                  <option value="recrute_les_deux">Recrute activement</option>
                  <option value="pas_de_recrutement">Pas de recrutement</option>
                </select>
              </div>
            </>
          ) : (
            <>
              <Field label="Titre professionnel" value={form.title} onChange={(v) => setKey("title", v)} testid="edit-title" />
              <Field label="École" value={form.school} onChange={(v) => setKey("school", v)} />
              <div>
                <Label>Niveau de diplôme</Label>
                <select value={form.level || ""} onChange={(e) => setKey("level", e.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="edit-level">
                  <option value="">Choisir un niveau</option>
                  {DIPLOMA_LEVELS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <Field label="Domaine" value={form.domain} onChange={(v) => setKey("domain", v)} />
              <Field label="Ville" value={form.city} onChange={(v) => setKey("city", v)} />
              <Field label="LinkedIn URL" value={form.linkedin_url} onChange={(v) => setKey("linkedin_url", v)} />
              <Field label="Photo URL" value={form.avatar} onChange={(v) => setKey("avatar", v)} />
              <div>
                <Label>Statut de recherche</Label>
                <select value={form.status || "en_recherche"} onChange={(e) => setKey("status", e.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="edit-status">
                  <option value="en_recherche">En recherche active</option>
                  <option value="a_l_ecoute">À l&apos;écoute</option>
                  <option value="deja_trouve">Déjà trouvé</option>
                  <option value="non_disponible">Non disponible</option>
                </select>
              </div>
            </>
          )}
          <div>
            <Label>Description</Label>
            <Textarea value={form.description || ""} onChange={(e) => setKey("description", e.target.value)} rows={4} className="rounded-xl mt-1" data-testid="edit-description" />
          </div>
          <Button onClick={onSave} className="rounded-xl bg-blue-600 hover:bg-blue-700 w-full" data-testid="save-profile">Enregistrer</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
