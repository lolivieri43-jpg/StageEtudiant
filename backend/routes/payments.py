"""Payments / Subscriptions routes — split from server.py.

Endpoints:
- GET  /api/subscriptions/me         — user's active subscription + tx history
- POST /api/subscriptions/cancel     — cancel active subscription
- POST /api/payments/checkout        — create Stripe checkout session
- GET  /api/payments/status/{id}     — poll checkout status (and fulfill on `paid`)
- POST /api/webhook/stripe           — Stripe webhook to confirm + fulfill
- GET  /api/admin/monetization       — KPI dashboard
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel


logger = logging.getLogger(__name__)

try:
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "sk_test_emergent")

# Fixed price packages (defined server-side only for security)
PACKAGES = {
    "sub_monthly": {"amount": 1.00, "currency": "eur", "kind": "subscription", "period": "monthly", "days": 30},
    "sub_yearly":  {"amount": 10.00, "currency": "eur", "kind": "subscription", "period": "yearly",  "days": 365},
    "boost_student": {"amount": 1.00, "currency": "eur", "kind": "boost", "actor": "candidate", "days": 7},
    "boost_company": {"amount": 10.00, "currency": "eur", "kind": "boost", "actor": "company", "days": 7},
}


class CheckoutIn(BaseModel):
    package_id: str
    origin_url: str
    deal_id: Optional[str] = None  # required for boosts


def register_payments_routes(api_router, db, get_current_user):
    async def fulfill_transaction(tx: dict):
        if tx.get("fulfilled"):
            return
        pkg_id = tx["package_id"]
        pkg = PACKAGES.get(pkg_id, {})
        now = datetime.now(timezone.utc)
        if pkg.get("kind") == "subscription":
            end = now + timedelta(days=pkg["days"])
            await db.subscriptions.update_many(
                {"company_id": tx["user_id"], "status": "active"},
                {"$set": {"status": "renewed"}},
            )
            await db.subscriptions.insert_one({
                "sub_id": f"sub_{uuid.uuid4().hex[:12]}",
                "company_id": tx["user_id"],
                "plan_type": pkg_id, "period": pkg["period"], "price": pkg["amount"],
                "status": "active",
                "start_date": now.isoformat(), "end_date": end.isoformat(),
                "renewal_date": end.isoformat(),
                "stripe_session_id": tx["session_id"],
                "created_at": now.isoformat(),
            })
        elif pkg.get("kind") == "boost":
            end = now + timedelta(days=pkg["days"])
            boost_field = "sponsored_until" if pkg["actor"] == "company" else "boosted_until"
            if tx.get("deal_id"):
                await db.deals.update_one({"deal_id": tx["deal_id"]},
                                          {"$set": {boost_field: end.isoformat()}})
            await db.boost_orders.insert_one({
                "boost_id": f"boost_{uuid.uuid4().hex[:12]}",
                "user_id": tx["user_id"], "user_type": tx["user_role"],
                "deal_id": tx.get("deal_id"),
                "boost_type": "sponsored" if pkg["actor"] == "company" else "highlight",
                "price": pkg["amount"], "duration_days": pkg["days"],
                "start_date": now.isoformat(), "end_date": end.isoformat(),
                "status": "active", "session_id": tx["session_id"],
                "created_at": now.isoformat(),
            })
        await db.payment_transactions.update_one({"tx_id": tx["tx_id"]},
                                                  {"$set": {"fulfilled": True}})
        await db.revenue_logs.insert_one({
            "log_id": f"rev_{uuid.uuid4().hex[:10]}",
            "amount": tx["amount"], "currency": tx["currency"], "kind": tx["kind"],
            "user_id": tx["user_id"], "package_id": pkg_id, "at": now.isoformat(),
        })

    @api_router.get("/subscriptions/me")
    async def my_subscription(user=Depends(get_current_user)):
        sub = await db.subscriptions.find_one(
            {"company_id": user["user_id"], "status": "active"}, {"_id": 0},
        )
        if sub and sub.get("end_date"):
            end = sub["end_date"]
            if isinstance(end, str):
                end_dt = datetime.fromisoformat(end)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                if end_dt < datetime.now(timezone.utc):
                    await db.subscriptions.update_one(
                        {"sub_id": sub["sub_id"]}, {"$set": {"status": "expired"}},
                    )
                    sub["status"] = "expired"
        history = await db.payment_transactions.find(
            {"user_id": user["user_id"]}, {"_id": 0},
        ).sort("created_at", -1).to_list(50)
        return {"subscription": sub, "history": history}

    @api_router.post("/subscriptions/cancel")
    async def cancel_sub(user=Depends(get_current_user)):
        sub = await db.subscriptions.find_one(
            {"company_id": user["user_id"], "status": "active"},
        )
        if not sub:
            raise HTTPException(404, "Aucun abonnement actif")
        await db.subscriptions.update_one(
            {"sub_id": sub["sub_id"]}, {"$set": {"status": "canceled"}},
        )
        return {"ok": True}

    @api_router.post("/payments/checkout")
    async def create_checkout(body: CheckoutIn, request: Request, user=Depends(get_current_user)):
        if not STRIPE_AVAILABLE:
            raise HTTPException(500, "Module de paiement indisponible")
        pkg = PACKAGES.get(body.package_id)
        if not pkg:
            raise HTTPException(400, "Package invalide")
        if pkg["kind"] == "subscription" and user["role"] != "company":
            raise HTTPException(403, "Réservé aux entreprises")
        if pkg["kind"] == "boost":
            if not body.deal_id:
                raise HTTPException(400, "deal_id requis")
            deal = await db.deals.find_one({"deal_id": body.deal_id}, {"_id": 0})
            if not deal:
                raise HTTPException(404, "Bon plan introuvable")
            if deal["author_id"] != user["user_id"]:
                raise HTTPException(403, "Pas votre bon plan")
            if pkg["actor"] == "candidate" and user["role"] != "candidate":
                raise HTTPException(403, "Boost étudiant réservé aux étudiants")
            if pkg["actor"] == "company" and user["role"] != "company":
                raise HTTPException(403, "Boost entreprise réservé aux entreprises")
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_co = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        origin = body.origin_url.rstrip("/")
        success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin}/payment/cancel"
        metadata = {
            "package_id": body.package_id,
            "user_id": user["user_id"],
            "user_role": user["role"],
            "kind": pkg["kind"],
        }
        if body.deal_id:
            metadata["deal_id"] = body.deal_id
        req = CheckoutSessionRequest(
            amount=pkg["amount"], currency=pkg["currency"],
            success_url=success_url, cancel_url=cancel_url, metadata=metadata,
        )
        session = await stripe_co.create_checkout_session(req)
        await db.payment_transactions.insert_one({
            "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
            "session_id": session.session_id,
            "user_id": user["user_id"], "user_role": user["role"],
            "package_id": body.package_id,
            "amount": pkg["amount"], "currency": pkg["currency"], "kind": pkg["kind"],
            "deal_id": body.deal_id, "metadata": metadata,
            "payment_status": "pending", "status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"url": session.url, "session_id": session.session_id}

    @api_router.get("/payments/status/{session_id}")
    async def payment_status(session_id: str, request: Request):
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not tx:
            raise HTTPException(404, "Transaction introuvable")
        if tx.get("payment_status") == "paid":
            return tx
        if not STRIPE_AVAILABLE:
            raise HTTPException(500, "Stripe indisponible")
        host_url = str(request.base_url).rstrip("/")
        stripe_co = StripeCheckout(api_key=STRIPE_API_KEY,
                                    webhook_url=f"{host_url}/api/webhook/stripe")
        try:
            res = await stripe_co.get_checkout_status(session_id)
        except Exception as e:
            logger.warning(f"Stripe status fetch failed for {session_id}: {e}")
            return tx
        new_status = res.payment_status
        upd = {"payment_status": new_status, "status": res.status}
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": upd})
        tx.update(upd)
        if new_status == "paid":
            await fulfill_transaction(tx)
        return tx

    @api_router.post("/webhook/stripe")
    async def stripe_webhook(request: Request):
        if not STRIPE_AVAILABLE:
            return {"ok": False}
        body = await request.body()
        sig = request.headers.get("Stripe-Signature")
        host_url = str(request.base_url).rstrip("/")
        stripe_co = StripeCheckout(api_key=STRIPE_API_KEY,
                                    webhook_url=f"{host_url}/api/webhook/stripe")
        try:
            evt = await stripe_co.handle_webhook(body, sig)
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return {"ok": False}
        if evt.payment_status == "paid":
            tx = await db.payment_transactions.find_one({"session_id": evt.session_id}, {"_id": 0})
            if tx and not tx.get("fulfilled"):
                await db.payment_transactions.update_one(
                    {"session_id": evt.session_id},
                    {"$set": {"payment_status": "paid", "status": "complete"}},
                )
                tx["payment_status"] = "paid"
                await fulfill_transaction(tx)
        return {"ok": True}

    @api_router.get("/admin/monetization")
    async def admin_monetization(user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        active_subs = await db.subscriptions.find({"status": "active"}, {"_id": 0}).to_list(500)
        monthly = sum(1 for s in active_subs if s.get("period") == "monthly")
        yearly = sum(1 for s in active_subs if s.get("period") == "yearly")
        revenue = await db.revenue_logs.find({}, {"_id": 0}).to_list(2000)
        total = sum(r["amount"] for r in revenue)
        boost_student_rev = sum(r["amount"] for r in revenue if r["package_id"] == "boost_student")
        boost_company_rev = sum(r["amount"] for r in revenue if r["package_id"] == "boost_company")
        sub_rev = sum(r["amount"] for r in revenue if r["kind"] == "subscription")
        failed = await db.payment_transactions.count_documents(
            {"payment_status": {"$in": ["failed", "expired"]}}
        )
        canceled = await db.subscriptions.count_documents({"status": "canceled"})
        transactions = await db.payment_transactions.find({}, {"_id": 0}).sort(
            "created_at", -1
        ).limit(50).to_list(50)
        return {
            "active_subs": len(active_subs),
            "monthly_subs": monthly, "yearly_subs": yearly,
            "total_revenue": total, "subscription_revenue": sub_rev,
            "boost_student_revenue": boost_student_rev,
            "boost_company_revenue": boost_company_rev,
            "failed_payments": failed, "canceled_subs": canceled,
            "transactions": transactions,
        }

    # Expose helper so other modules (e.g. routes/deals.py boost check) can reuse it
    register_payments_routes.fulfill_transaction = fulfill_transaction  # type: ignore[attr-defined]
