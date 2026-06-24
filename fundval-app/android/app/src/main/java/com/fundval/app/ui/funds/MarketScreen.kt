package com.fundval.app.ui.funds

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.fundval.app.data.api.dto.MarketIndex
import com.fundval.app.data.api.dto.RankingItem

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MarketScreen(
    viewModel: MarketViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("大盘与排行") })
        }
    ) { padding ->
        if (state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // Market indices row
                item {
                    Text("大盘指数", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        state.indices.forEach { index ->
                            MarketIndexCard(index)
                        }
                    }
                }

                // Rankings tabs
                item {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("排行榜", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                    TabRow(selectedTabIndex = when (state.rankingType) {
                        "popular" -> 1
                        "accuracy" -> 2
                        else -> 0
                    }) {
                        Tab(
                            selected = state.rankingType == "gain",
                            onClick = { viewModel.setRankingType("gain") },
                            text = { Text("涨幅榜") }
                        )
                        Tab(
                            selected = state.rankingType == "popular",
                            onClick = { viewModel.setRankingType("popular") },
                            text = { Text("人气榜") }
                        )
                        Tab(
                            selected = state.rankingType == "accuracy",
                            onClick = { viewModel.setRankingType("accuracy") },
                            text = { Text("准度榜") }
                        )
                    }
                }

                // Ranking list
                itemsIndexed(state.rankings) { index, item ->
                    RankingRow(index + 1, item)
                }
            }
        }
    }
}

@Composable
fun MarketIndexCard(index: MarketIndex) {
    Card(
        modifier = Modifier.width(150.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(index.name, style = MaterialTheme.typography.labelSmall)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = index.price ?: "-",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            val change = index.changePercent?.toDoubleOrNull()
            if (change != null) {
                Text(
                    text = "${growthFormat.format(change)}%",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (change >= 0) Color(0xFFE53935) else Color(0xFF43A047)
                )
            }
        }
    }
}

@Composable
fun RankingRow(rank: Int, item: RankingItem) {
    Surface(tonalElevation = 1.dp) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "$rank",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.width(32.dp)
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(item.fundName ?: "", style = MaterialTheme.typography.bodyMedium)
                Text(
                    "${item.fundCode} · ${item.fundType ?: ""}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            val growth = item.estimateGrowth?.toDoubleOrNull()
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
