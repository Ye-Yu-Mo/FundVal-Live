package com.fundval.app.ui.funds

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import java.text.DecimalFormat

val navFormat = DecimalFormat("0.0000")
val growthFormat = DecimalFormat("+0.00;-0.00")
val percentFormat = DecimalFormat("0.00")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FundDetailScreen(
    onNavigateBack: () -> Unit,
    viewModel: FundDetailViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.fund?.fundName ?: state.fundCode) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
                    }
                }
            )
        },
        contentWindowInsets = WindowInsets(0, 0, 0, 0)
    ) { padding ->
        if (state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else if (state.error != null && state.fund == null) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Text(state.error ?: "加载失败", color = MaterialTheme.colorScheme.error)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // Estimated NAV card (most important, always first)
                state.estimate?.let { estimate ->
                    item { EstimateCard(estimate) }
                }

                // Latest NAV card
                state.fund?.let { fund ->
                    item { NavCard(fund, state.estimate) }
                }

                // Intraday chart
                if (state.intraday.isNotEmpty()) {
                    item { IntradayChartCard(state.intraday) }
                }

                // Market quote (ETF only)
                state.marketQuote?.let { quote ->
                    if (quote.marketPrice != null) {
                        item { MarketQuoteCard(quote) }
                    }
                }

                // Holdings realtime
                if (state.holdings.isNotEmpty()) {
                    item { HoldingsCard(state.holdings) }
                }

                // Accuracy
                state.accuracy?.let { accuracy ->
                    item { AccuracyCard(accuracy) }
                }
            }
        }
    }
}

@Composable
fun EstimateCard(estimate: com.fundval.app.data.api.dto.EstimateResponse) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("实时估值", style = MaterialTheme.typography.labelMedium)
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = estimate.estimateNav ?: "-",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold
            )
            val growth = estimate.estimateGrowth?.toDoubleOrNull()
            if (growth != null) {
                val color = if (growth >= 0) Color(0xFFE53935) else Color(0xFF43A047)
                Text(
                    text = "${growthFormat.format(growth)}%",
                    style = MaterialTheme.typography.titleMedium,
                    color = color
                )
            }
            estimate.estimateTime?.let {
                Text(
                    text = "更新时间: $it",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f)
                )
            }
        }
    }
}

@Composable
fun NavCard(fund: com.fundval.app.data.api.dto.FundBrief, estimate: com.fundval.app.data.api.dto.EstimateResponse?) {
    Card {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text("最新净值", style = MaterialTheme.typography.labelMedium)
                Text(
                    text = fund.latestNav ?: "-",
                    style = MaterialTheme.typography.titleLarge
                )
                fund.latestNavDate?.let {
                    Text(
                        text = "日期: $it",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            // Arrow showing estimate vs actual
            val nav = fund.latestNav?.toDoubleOrNull()
            val est = estimate?.estimateNav?.toDoubleOrNull()
            if (nav != null && est != null) {
                val diff = est - nav
                val diffPercent = (diff / nav) * 100
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = growthFormat.format(diff),
                        style = MaterialTheme.typography.titleMedium,
                        color = if (diff >= 0) Color(0xFFE53935) else Color(0xFF43A047)
                    )
                    Text(
                        text = "(${growthFormat.format(diffPercent)}%)",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
fun IntradayChartCard(snapshots: List<com.fundval.app.data.api.dto.IntradaySnapshot>) {
    val values = snapshots.mapNotNull { it.estimateNav?.toDoubleOrNull() }
    if (values.isEmpty()) return

    Card {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("盘中估值曲线", style = MaterialTheme.typography.labelMedium)
            Spacer(modifier = Modifier.height(8.dp))

            val min = values.min()
            val max = values.max()
            val range = if (max - min == 0.0) 1.0 else max - min

            val lineColor = if (values.last() >= values.first()) Color(0xFFE53935) else Color(0xFF43A047)

            Canvas(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(160.dp)
            ) {
                if (values.size < 2) return@Canvas
                val stepX = size.width / (values.size - 1)
                val path = Path()
                values.forEachIndexed { i, v ->
                    val x = i * stepX
                    val y = size.height - ((v - min) / range * size.height).toFloat()
                    if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                drawPath(path, color = lineColor, style = Stroke(width = 3f, cap = StrokeCap.Round))
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(percentFormat.format(min), style = MaterialTheme.typography.labelSmall)
                Text(percentFormat.format(max), style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
fun MarketQuoteCard(quote: com.fundval.app.data.api.dto.MarketQuoteResponse) {
    Card {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("场内实时价格", style = MaterialTheme.typography.labelMedium)
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(quote.marketPrice ?: "-", style = MaterialTheme.typography.titleLarge)
                val growth = quote.marketGrowth?.toDoubleOrNull()
                if (growth != null) {
                    Text(
                        text = "${growthFormat.format(growth)}%",
                        style = MaterialTheme.typography.titleMedium,
                        color = if (growth >= 0) Color(0xFFE53935) else Color(0xFF43A047)
                    )
                }
            }
        }
    }
}

@Composable
fun HoldingsCard(holdings: List<com.fundval.app.data.api.dto.HoldingRealtime>) {
    Card {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("成分股实时行情", style = MaterialTheme.typography.labelMedium)
            Spacer(modifier = Modifier.height(8.dp))
            holdings.take(10).forEach { h ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(h.stockName, style = MaterialTheme.typography.bodyMedium)
                        Text(h.stockCode, style = MaterialTheme.typography.labelSmall)
                    }
                    Text("权重: ${h.weight}%", style = MaterialTheme.typography.bodySmall)
                    val change = h.changePercent?.toDoubleOrNull()
                    if (change != null) {
                        Text(
                            text = "${growthFormat.format(change)}%",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (change >= 0) Color(0xFFE53935) else Color(0xFF43A047)
                        )
                    }
                }
                HorizontalDivider()
            }
        }
    }
}

@Composable
fun AccuracyCard(accuracy: Map<String, com.fundval.app.data.api.dto.SourceAccuracy>) {
    Card {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("估值准确率", style = MaterialTheme.typography.labelMedium)
            Spacer(modifier = Modifier.height(8.dp))
            accuracy.forEach { (source, acc) ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(source, style = MaterialTheme.typography.bodyMedium)
                    Text("${acc.recordCount ?: 0} 条记录", style = MaterialTheme.typography.bodySmall)
                    acc.avgErrorRate?.let { rate ->
                        val rateDouble = rate.toDoubleOrNull()
                        Text(
                            text = "${percentFormat.format((rateDouble ?: 0.0) * 100)}%",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
        }
    }
}
