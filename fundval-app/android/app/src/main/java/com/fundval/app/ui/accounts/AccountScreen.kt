package com.fundval.app.ui.accounts

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.fundval.app.data.api.dto.AccountDto
import java.text.DecimalFormat

val moneyFormat = DecimalFormat("#,##0.00")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountScreen(
    viewModel: AccountViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsState()

    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("账户管理") },
            actions = {
                IconButton(onClick = { viewModel.showCreateDialog() }) {
                    Icon(Icons.Default.Add, "创建账户")
                }
            }
        )

        when {
            state.isLoading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            state.accounts.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("暂无账户", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            else -> {
                val flatItems = buildList {
                    state.accounts.forEach { parent ->
                        add(FlatAccountItem.Parent(parent))
                        if (state.expandedParents.contains(parent.id)) {
                            parent.children?.forEach { child ->
                                add(FlatAccountItem.Child(child))
                            }
                        }
                    }
                }
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(flatItems, key = { it.id }) { item ->
                        when (item) {
                            is FlatAccountItem.Parent -> AccountCard(
                                account = item.account,
                                isExpanded = state.expandedParents.contains(item.account.id),
                                hasChildren = !item.account.children.isNullOrEmpty(),
                                onToggle = { viewModel.toggleExpand(item.account.id) },
                                onDelete = { viewModel.requestDelete(item.account.id) }
                            )
                            is FlatAccountItem.Child -> AccountCard(
                                account = item.account,
                                isChild = true,
                                onDelete = { viewModel.requestDelete(item.account.id) }
                            )
                        }
                    }
                }
            }
        }
    }

    // Create dialog
    if (state.showCreateDialog) {
        var name by remember { mutableStateOf("") }
        var selectedParentId by remember { mutableStateOf<String?>(null) }
        var parentDropdownExpanded by remember { mutableStateOf(false) }
        val parentOptions = state.accounts // only parent accounts (they have no parent themselves)

        AlertDialog(
            onDismissRequest = { viewModel.hideCreateDialog() },
            title = { Text("创建账户") },
            text = {
                Column {
                    OutlinedTextField(
                        value = name,
                        onValueChange = { name = it },
                        label = { Text("账户名称") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(8.dp))
                    ExposedDropdownMenuBox(
                        expanded = parentDropdownExpanded,
                        onExpandedChange = { parentDropdownExpanded = it }
                    ) {
                        OutlinedTextField(
                            value = parentOptions.find { it.id == selectedParentId }?.name ?: "顶级账户（无父账户）",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("父账户") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(parentDropdownExpanded) },
                            modifier = Modifier.menuAnchor().fillMaxWidth()
                        )
                        ExposedDropdownMenu(expanded = parentDropdownExpanded, onDismissRequest = { parentDropdownExpanded = false }) {
                            DropdownMenuItem(
                                text = { Text("顶级账户（无父账户）") },
                                onClick = { selectedParentId = null; parentDropdownExpanded = false }
                            )
                            parentOptions.forEach { account ->
                                DropdownMenuItem(
                                    text = { Text(account.name) },
                                    onClick = { selectedParentId = account.id; parentDropdownExpanded = false }
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = { viewModel.createAccount(name, selectedParentId) },
                    enabled = name.isNotBlank()
                ) { Text("创建") }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.hideCreateDialog() }) { Text("取消") }
            }
        )
    }

    // Delete confirm dialog
    state.showDeleteInfo?.let { info ->
        AlertDialog(
            onDismissRequest = { viewModel.cancelDelete() },
            title = { Text("确认删除") },
            text = {
                Column {
                    info.message?.let { Text(it) }
                    info.childrenCount?.let { if (it > 0) Text("· 子账户: $it 个") }
                    info.positionsCount?.let { if (it > 0) Text("· 持仓: $it 个") }
                    info.totalCost?.let { Text("· 总成本: $it") }
                    if (info.canDelete.not()) {
                        Spacer(Modifier.height(8.dp))
                        Text("该账户不可删除", color = MaterialTheme.colorScheme.error)
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = { viewModel.confirmDelete() },
                    enabled = info.canDelete
                ) { Text("删除", color = if (info.canDelete) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface) }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.cancelDelete() }) { Text("取消") }
            }
        )
    }
}

private sealed class FlatAccountItem {
    abstract val id: String
    data class Parent(val account: AccountDto) : FlatAccountItem() {
        override val id get() = account.id
    }
    data class Child(val account: AccountDto) : FlatAccountItem() {
        override val id get() = account.id
    }
}

@Composable
fun AccountCard(
    account: AccountDto,
    isExpanded: Boolean = false,
    hasChildren: Boolean = false,
    isChild: Boolean = false,
    onToggle: (() -> Unit)? = null,
    onDelete: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = if (isChild) 24.dp else 0.dp)
            .then(if (onToggle != null && hasChildren) Modifier.clickable(onClick = onToggle) else Modifier)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (hasChildren) {
                        Icon(
                            if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Text(account.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                Row {
                    if (account.isDefault) {
                        Text("默认", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = onDelete, modifier = Modifier.size(32.dp)) {
                        Icon(Icons.Default.Delete, "删除", modifier = Modifier.size(18.dp))
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("持仓成本", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(moneyFormat.format(account.holdingCost?.toDoubleOrNull() ?: 0.0))
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("市值", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(moneyFormat.format(account.holdingValue?.toDoubleOrNull() ?: 0.0))
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("盈亏", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    val pnl = account.pnl?.toDoubleOrNull() ?: 0.0
                    Text(
                        moneyFormat.format(pnl),
                        color = if (pnl >= 0) Color(0xFFE53935) else Color(0xFF43A047)
                    )
                }
            }
        }
    }
}
