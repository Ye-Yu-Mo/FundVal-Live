package com.fundval.app.ui.funds

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CompareArrows
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.fundval.app.data.api.dto.FundBrief
import com.fundval.app.data.api.dto.MarketIndex
import com.fundval.app.data.api.dto.RankingItem
import java.text.DecimalFormat

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FundListScreen(
    onFundClick: (String) -> Unit,
    onNavigateToCompare: () -> Unit = {},
    viewModel: FundListViewModel = hiltViewModel(),
    marketViewModel: MarketViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsState()
    val marketState by marketViewModel.uiState.collectAsState()
    val listState = rememberLazyListState()
    var searchText by remember { mutableStateOf("") }
    var rankingExpanded by remember { mutableStateOf(false) }
    var rankingTab by remember { mutableIntStateOf(0) }

    val shouldLoadMore = remember {
        derivedStateOf {
            val lastVisibleItem = listState.layoutInfo.visibleItemsInfo.lastOrNull()
            lastVisibleItem != null && lastVisibleItem.index >= listState.layoutInfo.totalItemsCount - 3
        }
    }
    LaunchedEffect(shouldLoadMore.value) {
        if (shouldLoadMore.value) viewModel.loadMore()
    }

    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("基金浏览") },
            actions = {
                IconButton(onClick = onNavigateToCompare) {
                    Icon(Icons.Default.CompareArrows, "PK对比")
                }
            }
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Market indices header
            item {
                Text("大盘指数", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    marketState.indices.forEach { index ->
                        IndexMiniCard(index)
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Search bar
            item {
                OutlinedTextField(
                    value = searchText,
                    onValueChange = {
                        searchText = it
                        viewModel.onSearchQueryChange(it)
                    },
                    placeholder = { Text("搜索基金代码或名称") },
                    leadingIcon = { Icon(Icons.Default.Search, "搜索") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            // Rankings — collapsible, default collapsed
            if (marketState.rankings.isNotEmpty()) {
                item {
                    Surface(
                        modifier = Modifier.fillMaxWidth().clickable { rankingExpanded = !rankingExpanded },
                        tonalElevation = 1.dp
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("排行榜", style = MaterialTheme.typography.titleMedium)
                            Icon(
                                imageVector = if (rankingExpanded) Icons.Default.KeyboardArrowUp
                                    else Icons.Default.KeyboardArrowDown,
                                contentDescription = if (rankingExpanded) "收起" else "展开",
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                }

                if (rankingExpanded) {
                    item {
                        TabRow(selectedTabIndex = rankingTab) {
                            Tab(selected = rankingTab == 0, onClick = {
                                rankingTab = 0
                                marketViewModel.setRankingType("gain")
                            }, text = { Text("涨幅榜") })
                            Tab(selected = rankingTab == 1, onClick = {
                                rankingTab = 1
                                marketViewModel.setRankingType("popular")
                            }, text = { Text("人气榜") })
                            Tab(selected = rankingTab == 2, onClick = {
                                rankingTab = 2
                                marketViewModel.setRankingType("accuracy")
                            }, text = { Text("准度榜") })
                        }
                    }
                    items(marketState.rankings.take(10)) { item ->
                        RankingListItem(item = item, onClick = { onFundClick(item.fundCode) })
                    }
                }
            }

            // Fund results
            item {
                Text("基金列表", style = MaterialTheme.typography.titleMedium)
            }

            if (state.isRefreshing && state.funds.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(200.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator()
                    }
                }
            } else if (state.error != null && state.funds.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(state.error ?: "加载失败", color = MaterialTheme.colorScheme.error)
                            TextButton(onClick = { viewModel.refresh() }) { Text("重试") }
                        }
                    }
                }
            } else {
                items(state.funds, key = { it.fundCode }) { fund ->
                    FundListItem(fund = fund, onClick = { onFundClick(fund.fundCode) })
                }
                if (state.isLoading) {
                    item {
                        Box(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun IndexMiniCard(index: MarketIndex) {
    Card(
        modifier = Modifier.width(140.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(index.name, style = MaterialTheme.typography.labelSmall)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = index.price ?: "-",
                style = MaterialTheme.typography.titleSmall,
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
fun RankingListItem(item: RankingItem, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        tonalElevation = 1.dp
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
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

@Composable
fun FundListItem(fund: FundBrief, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        tonalElevation = 1.dp
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = fund.fundName,
                    style = MaterialTheme.typography.bodyLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "${fund.fundCode} · ${fund.fundType ?: ""}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(text = fund.latestNav ?: "-", style = MaterialTheme.typography.titleSmall)
                fund.latestNavDate?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}
