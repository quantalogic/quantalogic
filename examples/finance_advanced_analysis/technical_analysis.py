from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from loguru import logger

from quantalogic.tools import Tool, ToolArgument


class TechnicalAnalysisTool(Tool):
    """Performs comprehensive technical analysis with advanced indicators and trading zones."""

    name: str = "technical_analysis_tool"
    description: str = "Advanced technical analysis with multi-timeframe support"
    arguments: list[ToolArgument] = [
        ToolArgument(name="symbol", arg_type="string", description="Stock ticker symbol", required=True),
        ToolArgument(
            name="indicator",
            arg_type="string",
            description="Analysis type (sma/rsi/macd/liquidity/bollinger/fibonacci/stoch/levels)",
            required=True,
        ),
        ToolArgument(name="period", arg_type="int", description="Lookback period (positive integer)", required=True),
        ToolArgument(
            name="timeframe",
            arg_type="string",
            description="Time interval (1d/1h/15m/5m/1m)",
            required=False,
            default="1d",
        ),
        ToolArgument(
            name="start_date",
            arg_type="string",
            description="Start date (YYYY-MM-DD)",
            required=False,
            default=datetime.now().strftime("%Y-%m-%d"),
        ),
        ToolArgument(
            name="end_date",
            arg_type="string",
            description="End date (YYYY-MM-DD)",
            required=False,
            default=datetime.now().strftime("%Y-%m-%d"),
        ),
    ]

    def execute(
        self,
        symbol: str,
        indicator: str,
        period: int,
        timeframe: str = "1d",
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """Execute technical analysis with type-safe operations"""
        try:
            analysis_container = st.container(border=True)

            with analysis_container:
                period = self._validate_period(period)
                start_date, end_date = self._validate_dates(start_date, end_date)
                symbol = symbol.upper().strip()
                timeframe = self._validate_timeframe(timeframe)

                st.header(f"{symbol} Technical Analysis - {timeframe}", divider="rainbow")
                stock_data = self._fetch_stock_data(symbol=symbol, start=start_date, end=end_date, timeframe=timeframe)

                if stock_data.empty:
                    return f"No data found for {symbol}"

                indicator = indicator.lower()
                result_df = self._calculate_indicator(stock_data, indicator, period)
                self._display_analysis(result_df, symbol, indicator, period, timeframe)

                if indicator in ["liquidity", "levels"]:
                    self._show_trading_insights(result_df, symbol, indicator)

                return f"Successfully displayed {indicator.upper()} analysis for {symbol}"

        except Exception as e:
            st.error(f"Technical analysis failed: {str(e)}")
            return f"Analysis error: {str(e)}"

    def _validate_timeframe(self, timeframe: str) -> str:
        """Validate and normalize timeframe parameter"""
        valid_timeframes = {"1m", "5m", "15m", "1h", "1d"}
        timeframe = timeframe.lower()
        if timeframe not in valid_timeframes:
            raise ValueError(f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}")
        return timeframe

    def _fetch_stock_data(self, symbol: str, start: str, end: str, timeframe: str = "1d") -> pd.DataFrame:
        """Fetch and validate stock data with timeframe support"""
        with st.spinner(f"Fetching {symbol} {timeframe} data..."):
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(start=start, end=end, interval=timeframe)

                if hist.empty:
                    st.warning(f"No historical data found for {symbol}")
                    return pd.DataFrame()

                return hist.reset_index()
            except Exception as e:
                raise ValueError(f"Data fetch failed: {str(e)}")

    def _calculate_indicator(self, df: pd.DataFrame, indicator: str, period: int) -> pd.DataFrame:
        """Calculate the specified technical indicator"""
        calculators = {
            "sma": self._calculate_sma,
            "rsi": self._calculate_rsi,
            "macd": self._calculate_macd,
            "bollinger": self._calculate_bollinger,
            "fibonacci": self._calculate_fibonacci,
            "stoch": self._calculate_stochastic,
            "liquidity": self._calculate_liquidity_zones,
            "levels": self._calculate_key_levels,
        }

        if indicator not in calculators:
            raise ValueError(f"Unsupported indicator: {indicator}")

        return calculators[indicator](df, period)

    def _calculate_liquidity_zones(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate liquidity zones based on volume and price action"""
        with st.spinner("Analyzing liquidity zones..."):
            # Calculate volume profile
            df["Volume_MA"] = df["Volume"].rolling(window=period).mean()
            df["High_MA"] = df["High"].rolling(window=period).mean()
            df["Low_MA"] = df["Low"].rolling(window=period).mean()

            # Identify high volume nodes
            volume_std = df["Volume"].std()
            df["High_Volume_Node"] = df["Volume"] > (df["Volume_MA"] + volume_std)

            # Identify price swings
            df["Price_Range"] = df["High"] - df["Low"]
            df["Range_MA"] = df["Price_Range"].rolling(window=period).mean()

            # Detect potential liquidation levels
            df["Upper_Liquidity"] = df.apply(
                lambda x: x["High"] if x["High_Volume_Node"] and x["Price_Range"] > x["Range_MA"] * 1.5 else None,
                axis=1,
            )
            df["Lower_Liquidity"] = df.apply(
                lambda x: x["Low"] if x["High_Volume_Node"] and x["Price_Range"] > x["Range_MA"] * 1.5 else None, axis=1
            )

            return df

    def _calculate_key_levels(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate key trading levels including support, resistance, and liquidity pools"""
        with st.spinner("Calculating key trading levels..."):
            # Calculate pivot pointsanalyze   @
            df["PP"] = (df["High"] + df["Low"] + df["Close"]) / 3
            df["R1"] = 2 * df["PP"] - df["Low"]
            df["S1"] = 2 * df["PP"] - df["High"]
            df["R2"] = df["PP"] + (df["High"] - df["Low"])
            df["S2"] = df["PP"] - (df["High"] - df["Low"])

            # Calculate volume-weighted levels
            df["VWAP"] = (df["Close"] * df["Volume"]).cumsum() / df["Volume"].cumsum()

            # Identify swing points
            df["Swing_High"] = df.apply(
                lambda x: x["High"] if x["High"] == df["High"].rolling(window=period).max().iloc[-1] else None, axis=1
            )
            df["Swing_Low"] = df.apply(
                lambda x: x["Low"] if x["Low"] == df["Low"].rolling(window=period).min().iloc[-1] else None, axis=1
            )

            return df

    def _show_trading_insights(self, df: pd.DataFrame, symbol: str, indicator: str) -> None:
        """Display trading insights and key levels"""
        if indicator == "liquidity":
            self._display_liquidity_analysis(df, symbol)
        else:
            self._display_key_levels(df, symbol)

    def _display_liquidity_analysis(self, df: pd.DataFrame, symbol: str) -> None:
        """Display liquidation zones and volume analysis"""
        st.subheader("🎯 Liquidation Zones Analysis", divider="rainbow")

        # Recent liquidation levels
        recent_df = df.tail(10)
        upper_zones = recent_df[recent_df["Upper_Liquidity"].notna()]["Upper_Liquidity"]
        lower_zones = recent_df[recent_df["Lower_Liquidity"].notna()]["Lower_Liquidity"]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📈 Upper Liquidation Zones")
            for price in upper_zones:
                st.write(f"Price Level: ${price:.2f}")

        with col2:
            st.markdown("### 📉 Lower Liquidation Zones")
            for price in lower_zones:
                st.write(f"Price Level: ${price:.2f}")

        # Volume profile analysis
        st.markdown("### 📊 Volume Profile")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume", marker_color="rgba(0,255,0,0.1)"))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Volume_MA"], name="Volume MA", line=dict(color="yellow")))
        self._update_layout(fig, symbol, "Volume Profile")
        st.plotly_chart(fig, use_container_width=True)

    def _display_key_levels(self, df: pd.DataFrame, symbol: str) -> None:
        """Display key trading levels and pivot points"""
        st.subheader("🎯 Key Trading Levels", divider="rainbow")

        recent = df.iloc[-1]

        # Display current levels
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 📈 Resistance Levels")
            st.write(f"R2: ${recent['R2']:.2f}")
            st.write(f"R1: ${recent['R1']:.2f}")

        with col2:
            st.markdown("### ⚖️ Pivot Levels")
            st.write(f"PP: ${recent['PP']:.2f}")
            st.write(f"VWAP: ${recent['VWAP']:.2f}")

        with col3:
            st.markdown("### 📉 Support Levels")
            st.write(f"S1: ${recent['S1']:.2f}")
            st.write(f"S2: ${recent['S2']:.2f}")

        # Plot key levels
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="white", width=1)))

        # Add key levels
        for level, color in [
            ("R2", "red"),
            ("R1", "orange"),
            ("PP", "yellow"),
            ("VWAP", "purple"),
            ("S1", "lime"),
            ("S2", "green"),
        ]:
            fig.add_trace(go.Scatter(x=df["Date"], y=df[level], name=level, line=dict(color=color, dash="dash")))

        self._update_layout(fig, symbol, "Key Trading Levels")
        st.plotly_chart(fig, use_container_width=True)

    def _plot_fibonacci(self, df: pd.DataFrame, symbol: str) -> None:
        """Plot enhanced Fibonacci levels with trend analysis"""
        fig = go.Figure()

        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"
            )
        )

        # Fibonacci levels with labels
        levels = {
            "Fib_0": ("0%", "#FF0000"),
            "Fib_236": ("23.6%", "#FF9900"),
            "Fib_382": ("38.2%", "#FFFF00"),
            "Fib_500": ("50%", "#00FF00"),
            "Fib_618": ("61.8%", "#00FFFF"),
            "Fib_100": ("100%", "#FF00FF"),
            "Fib_1618": ("161.8%", "#9900FF"),
            "Fib_2618": ("261.8%", "#FF99FF"),
            "Fib_4236": ("423.6%", "#99FFFF"),
        }

        for level, (label, color) in levels.items():
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df[level],
                    name=f"Fib {label}",
                    line=dict(color=color, dash="dash"),
                    hovertemplate="Fib {label}: %{y:.2f}<extra></extra>",
                )
            )

        # Add volume profile
        fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume", marker_color="rgba(0,255,0,0.1)", yaxis="y2"))

        # Update layout with dual y-axis
        fig.update_layout(
            yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
            xaxis_rangeslider_visible=False,  # Hide rangeslider for cleaner look
        )

        self._update_layout(fig, symbol, "Fibonacci Analysis")
        st.plotly_chart(fig, use_container_width=True)

    def _calculate_macd(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Moving Average Convergence Divergence (MACD)

        Args:
            df: Price data
            period: Fast EMA period (slow will be 2x, signal will be 9)

        Returns:
            DataFrame with MACD indicators
        """
        try:
            # Calculate EMAs
            fast_ema = df["Close"].ewm(span=period, adjust=False).mean()
            slow_ema = df["Close"].ewm(span=period * 2, adjust=False).mean()

            # Calculate MACD line and signal line
            df["MACD"] = fast_ema - slow_ema
            df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
            df["MACD_Histogram"] = df["MACD"] - df["Signal"]

            return df

        except Exception as e:
            st.error(f"MACD calculation failed: {str(e)}")
            return df

    def _calculate_bollinger(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Bollinger Bands"""
        with st.spinner(f"Calculating Bollinger Bands ({period}-day)..."):
            df["SMA"] = df["Close"].rolling(window=period).mean()
            df["STD"] = df["Close"].rolling(window=period).std()
            df["Upper"] = df["SMA"] + (df["STD"] * 2)
            df["Lower"] = df["SMA"] - (df["STD"] * 2)
            return df[["Date", "Close", "SMA", "Upper", "Lower"]].dropna()

    def _calculate_fibonacci(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Fibonacci Retracement and Extension levels"""
        with st.spinner("Calculating Fibonacci levels..."):
            # Get swing high and low
            high = df["High"].rolling(window=period).max()
            low = df["Low"].rolling(window=period).min()
            diff = high - low

            # Retracement levels
            df["Fib_0"] = low
            df["Fib_236"] = low + diff * 0.236
            df["Fib_382"] = low + diff * 0.382
            df["Fib_500"] = low + diff * 0.500
            df["Fib_618"] = low + diff * 0.618
            df["Fib_100"] = high

            # Extension levels
            df["Fib_1618"] = high + diff * 0.618
            df["Fib_2618"] = high + diff * 1.618
            df["Fib_4236"] = high + diff * 2.618

            return df

    def _calculate_stochastic(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Stochastic Oscillator"""
        with st.spinner(f"Calculating Stochastic Oscillator ({period}-day)..."):
            low_min = df["Low"].rolling(window=period).min()
            high_max = df["High"].rolling(window=period).max()

            # Calculate %K
            df["K"] = 100 * ((df["Close"] - low_min) / (high_max - low_min))
            # Calculate %D (3-period SMA of %K)
            df["D"] = df["K"].rolling(window=3).mean()

            return df[["Date", "Close", "K", "D"]].dropna()

    def _display_analysis(self, df: pd.DataFrame, symbol: str, indicator: str, period: int, timeframe: str) -> None:
        """Display enhanced technical analysis with pattern recognition"""
        # Add pattern recognition
        patterns = self._detect_patterns(df)

        col1, col2 = st.columns([3, 1])

        with col1:
            if indicator == "fibonacci":
                self._plot_fibonacci(df, symbol)
            elif indicator == "bollinger":
                self._plot_bollinger(df, symbol, period)
            elif indicator == "macd":
                self._plot_macd(df, symbol)
            elif indicator == "stoch":
                self._plot_stochastic(df, symbol)
            else:
                self._plot_standard(df, symbol, indicator, period)

            if patterns:
                st.subheader("📊 Pattern Analysis")
                for pattern, confidence in patterns.items():
                    st.write(f"{pattern}: {confidence:.1%} confidence")

        with col2:
            st.dataframe(df.tail(10).style.format(precision=2), use_container_width=True, height=400)

            # Add market statistics
            self._display_market_stats(df)

    def _detect_patterns(self, df: pd.DataFrame) -> Dict[str, float]:
        """Detect candlestick patterns using price action analysis"""
        patterns = {}

        try:
            if len(df) >= 20:  # Ensure enough data points
                # Calculate basic candlestick patterns
                df["body"] = df["Close"] - df["Open"]
                df["upper_shadow"] = df["High"] - df[["Open", "Close"]].max(axis=1)
                df["lower_shadow"] = df[["Open", "Close"]].min(axis=1) - df["Low"]
                df["body_size"] = abs(df["body"])

                # Doji pattern (small body, longer shadows)
                avg_body = df["body_size"].mean()
                df["is_doji"] = (df["body_size"] < avg_body * 0.1) & (
                    (df["upper_shadow"] > df["body_size"]) | (df["lower_shadow"] > df["body_size"])
                )

                # Hammer pattern (small body, long lower shadow)
                df["is_hammer"] = (
                    (df["body_size"] < avg_body)
                    & (df["lower_shadow"] > df["body_size"] * 2)
                    & (df["upper_shadow"] < df["body_size"])
                )

                # Shooting Star pattern (small body, long upper shadow)
                df["is_shooting_star"] = (
                    (df["body_size"] < avg_body)
                    & (df["upper_shadow"] > df["body_size"] * 2)
                    & (df["lower_shadow"] < df["body_size"])
                )

                # Calculate pattern confidence based on recent signals
                pattern_cols = ["is_doji", "is_hammer", "is_shooting_star"]
                pattern_names = {"is_doji": "Doji", "is_hammer": "Hammer", "is_shooting_star": "Shooting Star"}

                for col in pattern_cols:
                    recent_signals = df[col].tail(5).mean()
                    if recent_signals > 0:
                        patterns[pattern_names[col]] = recent_signals

                # Add trend analysis
                df["sma20"] = df["Close"].rolling(window=20).mean()
                df["trend"] = np.where(df["Close"] > df["sma20"], "Bullish", "Bearish")
                trend_confidence = (df["trend"] == df["trend"].iloc[-1]).tail(5).mean()
                patterns[f'Trend ({df["trend"].iloc[-1]})'] = trend_confidence

                logger.info(f"Detected {len(patterns)} patterns with confidence levels")
        except Exception as e:
            logger.error(f"Pattern detection failed: {str(e)}")

        return patterns

    def _display_market_stats(self, df: pd.DataFrame) -> None:
        """Display key market statistics and momentum indicators"""
        try:
            st.subheader("📈 Market Statistics")

            # Calculate momentum indicators
            df["momentum"] = df["Close"].diff(14)
            df["roc"] = df["Close"].pct_change(14)

            # Recent performance
            latest_close = df["Close"].iloc[-1]
            prev_close = df["Close"].iloc[-2]
            daily_change = (latest_close - prev_close) / prev_close

            # Volatility
            df["returns"] = df["Close"].pct_change()
            volatility = df["returns"].std() * np.sqrt(252)  # Annualized volatility

            # Display stats
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Daily Change", f"{daily_change:.2%}")
                st.metric("Momentum (14)", f"{df['momentum'].iloc[-1]:.2f}")
            with col2:
                st.metric("Rate of Change", f"{df['roc'].iloc[-1]:.2%}")
                st.metric("Volatility (Ann.)", f"{volatility:.2%}")

            logger.info("Market statistics displayed successfully")
        except Exception as e:
            logger.error(f"Failed to display market stats: {str(e)}")

    def _plot_bollinger(self, df: pd.DataFrame, symbol: str, period: int) -> None:
        """Plot Bollinger Bands"""
        fig = go.Figure()

        fig.add_trace(go.Scatter(x=df["Date"], y=df["Upper"], name="Upper Band", line=dict(color="#00FF00")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA"], name=f"SMA {period}", line=dict(color="#FFFFFF")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Lower"], name="Lower Band", line=dict(color="#FF0000")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="#00FFFF")))

        self._update_layout(fig, symbol, f"Bollinger Bands ({period}-day)")
        st.plotly_chart(fig, use_container_width=True)

    def _plot_macd(self, df: pd.DataFrame, symbol: str) -> None:
        """Plot MACD indicator"""
        fig = go.Figure()

        fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="#FFFFFF")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], name="MACD", line=dict(color="#00FF00")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Signal"], name="Signal", line=dict(color="#FF0000")))

        self._update_layout(fig, symbol, "MACD")
        st.plotly_chart(fig, use_container_width=True)

    def _plot_stochastic(self, df: pd.DataFrame, symbol: str) -> None:
        """Plot Stochastic Oscillator"""
        fig = go.Figure()

        fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="#FFFFFF")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["K"], name="%K", line=dict(color="#00FF00")))
        fig.add_trace(go.Scatter(x=df["Date"], y=df["D"], name="%D", line=dict(color="#FF0000")))

        # Add overbought/oversold levels
        fig.add_hline(y=80, line_dash="dash", line_color="gray")
        fig.add_hline(y=20, line_dash="dash", line_color="gray")

        self._update_layout(fig, symbol, "Stochastic Oscillator")
        st.plotly_chart(fig, use_container_width=True)

    def _plot_standard(self, df: pd.DataFrame, symbol: str, indicator: str, period: int) -> None:
        """Plot standard indicators (SMA, RSI)"""
        fig = go.Figure()

        fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="#FFFFFF")))

        indicator_color = "#00FFAA" if indicator == "sma" else "#FFAA00"
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[indicator.upper()],
                name=f"{indicator.upper()} {period}",
                line=dict(color=indicator_color),
            )
        )

        if indicator == "rsi":
            fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.2)", line_width=0)
            fig.add_hline(y=30, line_dash="dash", line_color="red")
            fig.add_hline(y=70, line_dash="dash", line_color="red")

        self._update_layout(fig, symbol, f"{indicator.upper()} ({period}-day)")
        st.plotly_chart(fig, use_container_width=True)

    def _update_layout(self, fig: go.Figure, symbol: str, title: str) -> None:
        """Update plot layout with consistent styling"""
        fig.update_layout(
            title=f"{symbol} - {title}",
            xaxis_title="Date",
            yaxis_title="Price",
            template="plotly_dark",
            height=500,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )

    def _validate_period(self, period: int) -> int:
        """Convert and validate period parameter"""
        try:
            period = int(float(period))  # Handle numeric strings
            if period <= 0:
                raise ValueError("Period must be greater than 0")
            return period
        except (ValueError, TypeError):
            raise ValueError("Invalid period format - must be numeric")

    def _validate_dates(self, start: str, end: str) -> tuple[str, str]:
        """Validate and format date range"""
        try:
            start_dt = pd.to_datetime(start or datetime.now() - pd.DateOffset(years=1))
            end_dt = pd.to_datetime(end or datetime.now())

            if start_dt >= end_dt:
                raise ValueError("Start date must be before end date")

            return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("Invalid date format - use YYYY-MM-DD")

    def _calculate_sma(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Simple Moving Average"""
        with st.spinner(f"Calculating {period}-day SMA..."):
            df["SMA"] = df["Close"].rolling(window=period).mean()
            return df[["Date", "Close", "SMA"]].dropna()

    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Relative Strength Index with safe division"""
        with st.spinner(f"Calculating {period}-day RSI..."):
            delta = df["Close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            avg_gain = gain.rolling(period).mean()
            avg_loss = loss.rolling(period).mean()

            # Prevent division by zero
            avg_loss = avg_loss.replace(0.0, 1e-10)
            rs = avg_gain / avg_loss

            df["RSI"] = 100 - (100 / (1 + rs))
            return df[["Date", "Close", "RSI"]].dropna()
