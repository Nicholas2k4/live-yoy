import streamlit as st
st.set_page_config(page_title="GoodFellas Revenue YoY (Live)", layout="wide")

import pandas as pd
import numpy as np
from db_helper import DBHelper  # asumsi modul helper sudah ada
from auth_guard import check_auth

check_auth()

st.title("Revenue Comparison 2024 vs 2025 — per Branch (YoY)")

st.markdown("Pilih **branch** dari CSV master, lalu jalankan query live ke database (via SSH tunnel).")

# ----------------- Load Branch Master (CSV) -----------------
@st.cache_data
def load_branches_csv(file_or_path):
    dfb = pd.read_csv(file_or_path)
    # Validasi kolom minimal
    need = ["InternalID", "Branch_Name"]
    for c in need:
        if c not in dfb.columns:
            raise ValueError("CSV harus mengandung kolom: InternalID dan Branch_Name")
    use_cols = ["InternalID", "Branch_Name", "CompanyName", "City"]
    dfb = dfb[[c for c in use_cols if c in dfb.columns]].copy()

    dfb = dfb.dropna(subset=["InternalID", "Branch_Name"])
    dfb["InternalID"] = dfb["InternalID"].astype(int)

    # Label dropdown (tangani potensi duplikat nama)
    if "City" in dfb.columns:
        dfb["label"] = dfb.apply(lambda r: f"{r['Branch_Name']} — {r['City']}", axis=1)
    else:
        dfb["label"] = dfb["Branch_Name"].astype(str)
    return dfb

branches_df = None

if branches_df is None:
    # Fallback opsional: coba path lokal 'branches.csv'
    try:
        branches_df = load_branches_csv("Branch_Name_Address.csv")
    except Exception:
        st.warning("Silakan upload CSV master cabang terlebih dahulu (wajib kolom: InternalID, Branch_Name).", icon="⚠️")

if branches_df is not None:
    # ----------------- Form: pilih branch -----------------
    st.subheader("Revenue Comparison")
    with st.form("select_form"):
        labels = branches_df[["label", "InternalID"]].drop_duplicates().sort_values("label")
        label_to_id = dict(zip(labels["label"], labels["InternalID"]))
        selected_label = st.selectbox("Pilih Branch", list(label_to_id.keys()))
        selected_id = int(label_to_id[selected_label])
        submitted = st.form_submit_button("Run")

    # ----------------- Query & Analitik -----------------
    if submitted:
        sql = """
            SELECT
              YEAR(SalesDateIn)  AS y,
              MONTH(SalesDateIn) AS m,
              SUM(GrandTotal)    AS total_grand
            FROM ec_t_sales_header
            WHERE 
              CompanyInternalID = %s
              AND isFixed = 1
              AND SalesDateIn >= '2024-01-01' AND SalesDateIn < '2026-01-01'  -- ambil 2024 & 2025
              AND (
                StatusNota IN (6, 8, 9, 15, 16)
                OR (StatusNota = 12 AND StatusApproval IN (0, 2))
              )
            GROUP BY y, m
            ORDER BY y ASC, m ASC;
        """
        try:
            rows = DBHelper.query_live_db(sql, (selected_id,))
        except Exception as e:
            st.error(f"Gagal menjalankan query: {e}")
            rows = []

        st.caption(f"Branch: **{selected_label}** (InternalID = {selected_id})")
        st.write(f"Rows fetched: {len(rows)}")

        if not rows:
            st.warning("Tidak ada data untuk branch tersebut di periode 2024–2025.", icon="⚠️")
        else:
            df = pd.DataFrame(rows)  # kolom: y, m, total_grand
            # Pastikan numeric float (hindari Decimal vs float)
            df["total_grand"] = pd.to_numeric(df["total_grand"], errors="coerce").astype("float64")

            # Pivot: index=bulan (1..12), kolom=tahun (2024,2025)
            piv = (
                df.pivot_table(index="m", columns="y", values="total_grand", aggfunc="sum")
                  .reindex(range(1, 13))
                  .fillna(0.0)
            )
            # Pastikan kedua tahun ada
            for col in [2024, 2025]:
                if col not in piv.columns:
                    piv[col] = 0.0
            piv = piv[[2024, 2025]].astype("float64")

            # Hitung YoY: (2025-2024)/2024
            base = piv[2024].replace(0, np.nan)
            yoy = ((piv[2025] - piv[2024]) / base) * 100.0
            yoy = yoy.replace([np.inf, -np.inf], np.nan).fillna(0.0)

            out = piv.copy()
            out["Diff_Abs"] = out[2025] - out[2024]
            out["YoY_%"] = yoy

            bulan = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",7:"Jul",8:"Agu",9:"Sep",10:"Okt",11:"Nov",12:"Des"}
            out.index = out.index.map(lambda m: bulan.get(m, m))
            out = out.rename(columns={2024:"Total_2024", 2025:"Total_2025"})

            # Ringkasan metrik
            c1, c2, c3 = st.columns(3)
            total_2024 = float(out["Total_2024"].sum())
            total_2025 = float(out["Total_2025"].sum())
            yoy_total = (total_2025 - total_2024) / (total_2024 if total_2024 else np.nan) * 100.0
            yoy_total = 0.0 if np.isnan(yoy_total) else yoy_total
            c1.metric("Total 2024", f"Rp{total_2024:,.0f}")
            c2.metric("Total 2025", f"Rp{total_2025:,.0f}")
            c3.metric("YoY Total", f"{yoy_total:+.2f}%")

            st.subheader("Revenue per Bulan & Growth YoY")
            st.dataframe(
                out.style.format({
                    "Total_2024": "Rp{:,.0f}",
                    "Total_2025": "Rp{:,.0f}",
                    "Diff_Abs":   "Rp{:,.0f}",
                    "YoY_%":      "{:+.2f}%"
                })
            )

            # st.subheader("Perbandingan Revenue Bulanan (2024 vs 2025)")
            # st.line_chart(out[["Total_2024", "Total_2025"]])

            # st.subheader("YoY Growth per Bulan (%)")
            # st.bar_chart(out[["YoY_%"]])

