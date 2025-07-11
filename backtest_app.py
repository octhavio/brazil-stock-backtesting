import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, timedelta

st.set_page_config(layout="wide")
st.title("📈 Backtesting de Carteira de Ações")

# ⚙️ Parâmetros padrão (mantemos .SA internamente)
DEFAULT_TICKERS = [
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

# 🔄 Função de rerun compatível
def do_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()

# 🗓️ Cache do primeiro dia de negociação
@st.cache_data(show_spinner=False)
def get_first_trade_date(ticker: str):
    """Retorna a data do primeiro pregão do ticker (ou None)."""
    try:
        info = yf.Ticker(ticker).info
        epoch = info.get("firstTradeDateEpochUtc")
        if epoch:
            return pd.to_datetime(epoch, unit="s").date()
    except Exception:
        pass
    return None

# 📌 Session state
if "tickers" not in st.session_state:
    st.session_state.tickers = DEFAULT_TICKERS.copy()

end_date = date.today()
start_date = end_date - timedelta(days=365 * 10)

# ────────────────────────────────────────────────────────────────
# 🎯 Interface do usuário
# ────────────────────────────────────────────────────────────────
st.header("🛠️ Configuração da Carteira")

col_input, col_add = st.columns([3, 1])
with col_input:
    new_ticker = st.text_input("Adicionar ticker (ex.: PETR4)")
with col_add:
    if st.button("➕ Adicionar", use_container_width=True):
        raw = new_ticker.strip().upper()
        if raw:
            if "." not in raw and not raw.startswith("^"):
                raw += ".SA"
            if raw not in st.session_state.tickers:
                st.session_state.tickers.append(raw)
                do_rerun()

# 🌟 Exibição compacta dos tickers como badges
if st.session_state.tickers:
    st.markdown("### 📋 Tickers atuais")
    badge_rows = [st.session_state.tickers[i : i + 6] for i in range(0, len(st.session_state.tickers), 6)]
    for row in badge_rows:
        cols = st.columns(len(row))
        for idx, tic in enumerate(row):
            label = tic.replace(".SA", "")
            if cols[idx].button(f"{label} ✕", key=f"rem_{tic}", use_container_width=True):
                st.session_state.tickers.remove(tic)
                do_rerun()

col1, col2 = st.columns(2)
with col1:
    start = st.date_input("Data de início", value=start_date)
with col2:
    end = st.date_input("Data de fim", value=end_date)

# 🎒 Pesos iguais
tickers = st.session_state.tickers
weights = [1 / len(tickers)] * len(tickers) if tickers else []

if not tickers:
    st.warning("Adicione pelo menos um ticker para rodar o backtest.")

# ────────────────────────────────────────────────────────────────
# 🔁 Backtest
# ────────────────────────────────────────────────────────────────
if st.button("🔁 Rodar Backtest", type="primary") and tickers:
    try:
        # 1) Dados da carteira --------------------------------------------------
        raw_data = yf.download(
            tickers,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
        )["Adj Close"]

        if isinstance(raw_data, pd.Series):
            raw_data = raw_data.to_frame(name=tickers[0])

        if isinstance(raw_data.columns, pd.MultiIndex):
            raw_data.columns = raw_data.columns.droplevel(0)

        # 2) Limpa datas ANTES da listagem ---------------------------
        cleaned = raw_data.copy()
        for col in cleaned.columns:
            first_trade = get_first_trade_date(col)
            if first_trade:
                cleaned.loc[cleaned.index.date < first_trade, col] = pd.NA
            cleaned.loc[cleaned[col] < 0.1, col] = pd.NA
        portfolio_data = cleaned

        # 3) Benchmark (Ibovespa) ------------------------------------
        benchmark_ticker = "^BVSP"
        benchmark_data = yf.download(
            benchmark_ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
        )["Adj Close"]

        # 4) Alinhar datas ------------------------------------------
        combined = pd.concat([portfolio_data, benchmark_data], axis=1, join="inner")
        combined = combined.sort_index()
        portfolio_data = combined[tickers].dropna(how="all")
        benchmark_data = combined[benchmark_ticker]

        # 5) Normalizar coluna a coluna (primeiro valor válido) ------
        def normalize_col(col):
            first_valid = col.first_valid_index()
            return col / col.loc[first_valid]

        normalized_port = portfolio_data.apply(normalize_col, axis=0)
        portfolio = (normalized_port * weights).sum(axis=1)
        benchmark_norm = benchmark_data / benchmark_data.iloc[0]

        # 6) Gráfico -------------------------------------------------
        st.subheader("📊 Retorno acumulado: Carteira vs. Ibovespa")
        fig, ax = plt.subplots(figsize=(12, 5))
        portfolio.plot(ax=ax, label="Carteira")
        benchmark_norm.loc[portfolio.index].plot(ax=ax, label="Ibovespa")
        ax.set_ylabel("Retorno acumulado (base 100)")
        ax.grid(True)
        ax.legend()
        st.pyplot(fig)

        # 7) Estatísticas -------------------------------------------
        st.subheader("📌 Estatísticas da Carteira")
        total_return = portfolio[-1] / portfolio[0] - 1
        annualized_return = (portfolio[-1] / portfolio[0]) ** (1 / ((end - start).days / 365)) - 1
        st.markdown(f"- **Retorno total:** {total_return:.2%}")
        st.markdown(f"- **Retorno anualizado:** {annualized_return:.2%}")

        st.subheader("📌 Estatísticas do Ibovespa")
        ibov_total = benchmark_norm.loc[portfolio.index][-1] - 1
        ibov_annual = benchmark_norm.loc[portfolio.index][-1] ** (1 / ((end - start).days / 365)) - 1
        st.markdown(f"- **Retorno total:** {ibov_total:.2%}")
        st.markdown(f"- **Retorno anualizado:** {ibov_annual:.2%}")

        # 8) Tabela base 100 ----------------------------------------
        st.subheader("📋 Dados utilizados (base 100)")
        table_norm = normalized_port.copy()
        table_norm["Carteira"] = portfolio
        table_norm["Ibovespa"] = benchmark_norm.loc[portfolio.index]
        st.dataframe(table_norm.sort_index())

        st.download_button(
            "⬇️ Baixar CSV (base 100)",
            data=table_norm.to_csv().encode("utf-8"),
            file_name="backtest_base100.csv",
            mime="text/csv",
        )

        # 9) Tabela de cotações -------------------------------------
        st.subheader("📋 Cotações ajustadas (R$)")
        price_df = portfolio_data.copy()
        price_df["Ibovespa"] = benchmark_data
        st.dataframe(price_df.sort_index())

        st.download_button(
            "⬇️ Baixar CSV (cotações)",
            data=price_df.to_csv().encode("utf-8"),
            file_name="backtest_quotes.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Erro ao executar o backtest: {str(e)}")
