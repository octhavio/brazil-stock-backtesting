import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, timedelta

st.set_page_config(layout="wide")
st.title("📈 Backtesting de Carteira de Ações")

# ⚙️ Parâmetros padrão
default_tickers = [
    "BBAS3.SA",
    "SAPR11.SA",
    "TAEE11.SA",
    "VALE3.SA",
    "BBSE3.SA",
    "CSMG3.SA",
    "ITSA4.SA",
    "ISAE4.SA",
    "CMIG4.SA",
]

# 👉 Session state para persistir tickers na página
if "tickers" not in st.session_state:
    st.session_state.tickers = default_tickers.copy()

end_date = date.today()
start_date = end_date - timedelta(days=365 * 10)

# ────────────────────────────────────────────────────────────────
# 🎯 Interface do usuário
# ────────────────────────────────────────────────────────────────
st.header("🛠️ Configuração da Carteira")

col_input, col_add = st.columns([3, 1])
with col_input:
    new_ticker = st.text_input("Adicionar ticker (ex.: PETR4.SA)")
with col_add:
    if st.button("➕ Adicionar"):
        t = new_ticker.strip().upper()
        if t and t not in st.session_state.tickers:
            st.session_state.tickers.append(t)
            st.experimental_rerun()

st.markdown("### 📋 Tickers atuais")
for idx, tic in enumerate(st.session_state.tickers):
    col_tic, col_rem = st.columns([3, 1])
    col_tic.write(f"- {tic}")
    if col_rem.button("🗑️", key=f"remove_{tic}"):
        st.session_state.tickers.pop(idx)
        st.experimental_rerun()

col1, col2 = st.columns(2)
with col1:
    start = st.date_input("Data de início", value=start_date)
with col2:
    end = st.date_input("Data de fim", value=end_date)

# 🎒 Calcula pesos iguais automaticamente

tickers = st.session_state.tickers
weights = [1 / len(tickers)] * len(tickers) if tickers else []

if not tickers:
    st.warning("Adicione pelo menos um ticker para rodar o backtest.")

# ────────────────────────────────────────────────────────────────
# 🔁 Backtest
# ────────────────────────────────────────────────────────────────
if st.button("🔁 Rodar Backtest") and tickers:
    try:
        # 1) Baixa dados da carteira
        portfolio_data = yf.download(
            tickers,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
        )["Adj Close"]

        # Garante DataFrame (quando há 1 ticker volta Series)
        if isinstance(portfolio_data, pd.Series):
            portfolio_data = portfolio_data.to_frame(name=tickers[0])

        # Remove o nível superior do MultiIndex, se houver
        if isinstance(portfolio_data.columns, pd.MultiIndex):
            portfolio_data.columns = portfolio_data.columns.droplevel(0)

        # 2) Baixa benchmark (Ibovespa)
        benchmark_ticker = "^BVSP"
        benchmark_data = yf.download(
            benchmark_ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
        )["Adj Close"]

        # 3) Combina e alinha datas
        combined = pd.concat([portfolio_data, benchmark_data], axis=1, join="inner")
        portfolio_data = combined[tickers]
        benchmark_data = combined[benchmark_ticker]

        # 4) Normaliza (base 100)
        normalized_port = portfolio_data / portfolio_data.iloc[0]
        portfolio = (normalized_port * weights).sum(axis=1)
        benchmark_norm = benchmark_data / benchmark_data.iloc[0]

        # 5) Gráfico
        st.subheader("📊 Retorno acumulado: Carteira vs. Ibovespa")
        fig, ax = plt.subplots(figsize=(12, 5))
        portfolio.plot(ax=ax, label="Carteira")
        benchmark_norm.plot(ax=ax, label="Ibovespa")
        ax.set_ylabel("Retorno acumulado (base 100)")
        ax.grid(True)
        ax.legend()
        st.pyplot(fig)

        # 6) Estatísticas
        st.subheader("📌 Estatísticas da Carteira")
        total_return = portfolio[-1] / portfolio[0] - 1
        annualized_return = (portfolio[-1] / portfolio[0]) ** (1 / ((end - start).days / 365)) - 1
        st.markdown(f"- **Retorno total:** {total_return:.2%}")
        st.markdown(f"- **Retorno anualizado:** {annualized_return:.2%}")

        st.subheader("📌 Estatísticas do Ibovespa")
        ibov_total = benchmark_norm[-1] - 1
        ibov_annual = benchmark_norm[-1] ** (1 / ((end - start).days / 365)) - 1
        st.markdown(f"- **Retorno total:** {ibov_total:.2%}")
        st.markdown(f"- **Retorno anualizado:** {ibov_annual:.2%}")

        # 7) Tabela base 100
        st.subheader("📋 Dados utilizados (base 100)")
        table_df = normalized_port.copy()
        table_df["Carteira"] = portfolio
        table_df["Ibovespa"] = benchmark_norm
        st.dataframe(table_df)

        # Download CSV
        csv = table_df.to_csv().encode("utf-8")
        st.download_button(
            "⬇️ Baixar CSV",
            data=csv,
            file_name="backtest_data.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Erro ao executar o backtest: {str(e)}")
