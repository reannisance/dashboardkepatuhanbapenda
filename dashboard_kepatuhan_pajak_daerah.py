import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import plotly.express as px

st.set_page_config(page_title="🎨 Dashboard Kepatuhan Pajak Daerah", layout="wide")
st.title("🎯 Dashboard Kepatuhan Pajak Daerah")
st.markdown("Upload file Excel, pilih sheet, filter, dan lihat visualisasinya ✨")

uploaded_file = st.file_uploader("📁 Upload File Excel", type=["xlsx"])
tahun_pajak = st.number_input("📅 Pilih Tahun Pajak", min_value=2000, max_value=2100, value=2024)

def hitung_kepatuhan(df, tahun_pajak):
    df['TMT'] = pd.to_datetime(df['TMT'], errors='coerce')
    payment_cols = [col for col in df.columns if isinstance(col, datetime) and col.year == tahun_pajak]

    total_pembayaran = df[payment_cols].sum(axis=1)

    def hitung_bulan_aktif(tmt):
        if pd.isna(tmt): return 0
        if tmt.year < tahun_pajak:
            return 12
        elif tmt.year > tahun_pajak:
            return 0
        else:
            return 12 - tmt.month + 1

    bulan_aktif = df['TMT'].apply(hitung_bulan_aktif)
    bulan_pembayaran = df[payment_cols].gt(0).sum(axis=1)
    rata_rata_pembayaran = total_pembayaran / bulan_pembayaran.replace(0, 1)
    kepatuhan_persen = bulan_pembayaran / bulan_aktif.replace(0, 1) * 100

    def klasifikasi(row):
        if row['bulan_aktif'] == 0 and row['bulan_pembayaran'] == 0:
            return "Belum Aktif"
        elif row['bulan_pembayaran'] == row['bulan_aktif']:
            return "Patuh"
        elif row['bulan_aktif'] - row['bulan_pembayaran'] <= 3:
            return "Kurang Patuh"
        else:
            return "Tidak Patuh"

    df["Total Pembayaran"] = total_pembayaran
    df["bulan_aktif"] = bulan_aktif
    df["bulan_pembayaran"] = bulan_pembayaran
    df["Rata-rata Pembayaran"] = rata_rata_pembayaran
    df["Kepatuhan (%)"] = kepatuhan_persen
    df["Klasifikasi Kepatuhan"] = df.apply(klasifikasi, axis=1)

    return df, payment_cols

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    selected_sheet = st.selectbox("📄 Pilih Nama Sheet", sheet_names)
    df_input = pd.read_excel(xls, sheet_name=selected_sheet)

# Baca data
df_input = pd.read_excel(xls, sheet_name=selected_sheet)

# Normalisasi nama kolom agar tahan terhadap kapitalisasi dan spasi
df_input.columns = df_input.columns.str.strip().str.lower()

# Buat mapping nama standar ke nama sebenarnya
col_mapping = {
    'tmt': None,
    'nama op': None,
    'nm unit': None,
    'klasifikasi': None,
    'status': None
}

# Cari kolom yang cocok dari versi lowercase
for col in df_input.columns:
    for key in col_mapping:
        if key.replace(" ", "") == col.replace(" ", ""):
            col_mapping[key] = col

# Validasi kolom wajib
required_keys = ['tmt', 'nama op', 'nm unit', 'klasifikasi']
missing_keys = [key for key in required_keys if col_mapping[key] is None]

if missing_keys:
    st.error(f"❌ Kolom wajib hilang: {', '.join(missing_keys)}. Harap periksa file Anda.")
else:
    # Rename ke nama baku agar kode lama tetap jalan
    df_input_renamed = df_input.rename(columns={v: k.title() for k, v in col_mapping.items() if v})
    df_output, payment_cols = hitung_kepatuhan(df_input_renamed.copy(), tahun_pajak)

    
    required_cols = ["TMT", "Nm Unit", "KLASIFIKASI"]
    missing_cols = [col for col in required_cols if col not in df_input.columns]

    if missing_cols:
        st.error(f"❌ Kolom wajib hilang: {', '.join(missing_cols)}. Harap periksa file Anda.")
    else:
        df_output, payment_cols = hitung_kepatuhan(df_input.copy(), tahun_pajak)

        with st.sidebar:
            st.header("🔍 Filter Data")
            selected_unit = st.selectbox("🏢 Pilih UPPPD", ["Semua"] + sorted(df_output["Nm Unit"].dropna().unique().tolist()))
            if selected_unit != "Semua":
                df_output = df_output[df_output["Nm Unit"] == selected_unit]

            selected_klasifikasi = st.selectbox("📂 Pilih Klasifikasi Pajak", ["Semua"] + sorted(df_output["KLASIFIKASI"].dropna().unique().tolist()))
            if selected_klasifikasi != "Semua":
                df_output = df_output[df_output["KLASIFIKASI"] == selected_klasifikasi]

            if "Status" in df_output.columns:
                selected_status = st.multiselect("📌 Pilih Status OP", options=sorted(df_output["Status"].dropna().unique().tolist()), default=None)
                if selected_status:
                    df_output = df_output[df_output["Status"].isin(selected_status)]

        st.success("✅ Data berhasil diproses dan difilter!")
        st.dataframe(df_output.head(30), use_container_width=True)

        output = BytesIO()
        df_output.to_excel(output, index=False)
        st.download_button("⬇️ Download Hasil Excel", data=output.getvalue(), file_name="hasil_dashboard.xlsx")

        st.subheader("Pie Chart Kepatuhan WP")
        pie_data = df_output["Klasifikasi Kepatuhan"].value_counts().reset_index()
        pie_data.columns = ["Klasifikasi", "Jumlah"]
        fig_pie = px.pie(
            pie_data,
            names="Klasifikasi",
            values="Jumlah",
            title="Distribusi Kepatuhan WP",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📈 Tren Pembayaran Pajak per Bulan")
        if payment_cols:
            bulanan = df_output[payment_cols].sum().reset_index()
            bulanan.columns = ["Bulan", "Total Pembayaran"]
            bulanan["Bulan"] = pd.to_datetime(bulanan["Bulan"])
            bulanan = bulanan.sort_values("Bulan")

            fig_line = px.line(
                bulanan,
                x="Bulan",
                y="Total Pembayaran",
                title="Total Pembayaran Pajak per Bulan",
                markers=True,
                line_shape="spline",
                color_discrete_sequence=["#FFB6C1"]
            )
            st.plotly_chart(fig_line, use_container_width=True)

            st.subheader("🏅 Top 5 Objek Pajak Berdasarkan Total Pembayaran (Tabel Lengkap)")
            
            # Ambil kolom yang dibutuhkan
            top_wp_detail = (
                df_output[["Nama Op", "Total Pembayaran", "Nm Unit", "KLASIFIKASI"]]
                .groupby(["Nama Op", "Nm Unit", "KLASIFIKASI"], as_index=False)
                .sum()
                .sort_values("Total Pembayaran", ascending=False)
                .head(5)
            )
            
            # Tampilkan sebagai tabel
            st.dataframe(top_wp_detail.style.format({"Total Pembayaran": "Rp{:,.0f}"}), use_container_width=True)

