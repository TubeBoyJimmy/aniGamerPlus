var dataArrays; //用户配置json
var proxy_protocol;
var proxy_ip;
var proxy_port;
var proxy_user = '';
var proxy_passwd = '';
id_list.push('proxy_protocol', 'proxy_ip', 'proxy_port', 'proxy_user', 'proxy_passwd');

$.ajax({
	type: "get",
	url: "data/config.json",
	dataType: "json",
	async: true,
	success: function(data) {
		dataArrays = data;
		parseProxy(data.proxy);
		$(function (){
			renderJson();
		});
	}
});

showSnList();

function parseProxy(proxy) {
	proxy_protocol = proxy.replace(/:\/\/.*/i, '').toUpperCase();
	if (/.*@.*/.test(proxy)) {
		proxy_user = /:\/\/.*?:/g.exec(proxy)[0].replace(/:(\/\/)?/g, '');
		proxy_passwd = /:.*@/.exec(proxy)[0].replace(proxy_user, '')
			.replace(/(:\/\/:)?@?/g, '');
		proxy = proxy.replace(proxy_user + ':' + proxy_passwd + '@', '');
	}
	var tmp = proxy.replace(/.*:\/\//i, '');
	if (proxy.length > 0) {
		proxy_ip = /:.*:/.exec(proxy)[0].replace(/:(\/\/)?/g, '');
		proxy_port = /:\d+/.exec(proxy)[0].replace(/:/, '');
	} else {
		proxy_ip = '';
		proxy_port = '';
	}
	
	dataArrays.proxy_protocol = proxy_protocol;
	dataArrays.proxy_ip = proxy_ip;
	dataArrays.proxy_port = proxy_port;
	dataArrays.proxy_user = proxy_user;
	dataArrays.proxy_passwd = proxy_passwd;
}

function reloadSetting() {
	readJson();
	renderJson();
}

function readJson() {
	$.getJSON("data/config.json", function(data) {
		dataArrays = data;
		parseProxy(data.proxy); // 解析代理配置
	});
}

function renderJson() {
	for (var id of id_list) {
		if (id == 'proxy') continue; //代理设置已被分解
		var idType = document.getElementById(id).type;
		switch (idType) {
			case 'text':
			case 'number':
			case 'password':
				if (id  == 'multi-thread')  // 手动任务的默认线程数
					$('#manual_thread_limit').val(dataArrays[id]);
				$("#" + id).val(dataArrays[id]);
				break;
			case 'checkbox':
				$("#" + id).bootstrapSwitch('state', dataArrays[id]);
				break;
			case 'select-one':
				if (id == 'proxy_protocol') {
					$("#" + id).selectpicker('val', dataArrays[id].toUpperCase());
				} else {
					$("#" + id).find("option:contains('" + dataArrays[id] + "')")
						.prop("selected", true);
					$("#" + id).selectpicker('render');
				}
				break;

		}
	}
}


function readSettings() {
	for (var id of id_list) {
		if (id == 'proxy') continue; //代理设置已被分解

		var idType = document.getElementById(id).type;
		switch (idType) {
			case 'number':
				dataArrays[id] = Number($("#" + id).val());
				break;
			case 'text':
			case 'password':
				dataArrays[id] = $("#" + id).val();
				break;
			case 'checkbox':
				dataArrays[id] = $("#" + id).is(":checked");
				break;
			case 'select-one':
				if (id == 'proxy_protocol') {
					dataArrays[id] = $("#proxy_protocol").val().toLowerCase();
				} else if (id == 'download_resolution') {
					dataArrays[id] = $("#download_resolution").val().replace('P', '');
				} else {
					dataArrays[id] = $("#" + id).val();
				}
				break;
		}

		// 合并代理配置
		var a = ['proxy_protocol', 'proxy_ip', 'proxy_port', 'proxy_user', 'proxy_passwd'];
		for (var i in a) {
			var ip_port = dataArrays["proxy_ip"] + ':' + dataArrays["proxy_port"];
			var protocol = dataArrays["proxy_protocol"] + '://';
			if (dataArrays["proxy_user"]?.length * dataArrays["proxy_passwd"]?.length == 0) {
				// 如果没有用户密码
				dataArrays["proxy"] = protocol + ip_port;
			} else {
				// 如果有用户密码
				var user_pw = dataArrays["proxy_user"] + ':' + dataArrays["proxy_passwd"] + '@';
				dataArrays["proxy"] = protocol + user_pw + ip_port;
			}

		}
	}

	$.ajax({
		url: '/uploadConfig',
		type: 'post',
		dataType: 'json',
		headers: {
			"Content-Type": "application/json;charset=utf-8"
		},
		contentType: 'application/json; charset=utf-8',
		data: JSON.stringify(dataArrays),
		success: function(data) {
			// 向用户提示提交成功
			$('#uploadOk').show();
			$('#uploadFailed').hide();
			$('#uploadStatus').modal();
			reloadSetting();
		},
		error:function(status){
			// 向用户提示提交失败
			$('#uploadOk').hide();
			$('#uploadFailed').show();
			$('#uploadStatus').modal();
		}
	})
}

function getUA(){
	$('#ua').val(navigator.userAgent);
	alert("已取得當前瀏覽器UA");
}

function readManualConfig(){
	var manualData = {};
	var link = $('#manual_link').val();
	if (link.length == 0) {
		alert('請輸入影片鏈接！')
	} else {
		var sn = link.replace(/(https:\/\/)?ani\.gamer\.com\.tw\/animeVideo\.php\?sn=/i, '');
		manualData['sn'] = sn;
		
		var mode = $("#manual_mode").val();
		manualData['mode'] = mode;
		
		var resolution = $('#manual_resolution').val().replace('P', '');
		manualData['resolution'] = resolution;
		
		var classify = $('#manual_classify').is(":checked");
		manualData['classify'] = classify;
		
		var thread = $('#manual_thread_limit').val();
		manualData['thread'] = thread;

		var danmu = $('#manual_danmu').is(":checked");
		manualData['danmu'] = danmu;
		
		$.ajax({
			url: '/manualTask',
			type: 'post',
			dataType: 'json',
			headers: {
				"Content-Type": "application/json;charset=utf-8"
			},
			contentType: 'application/json; charset=utf-8',
			data: JSON.stringify(manualData),
			success: function(data) {
				// 向用户提示提交成功
				$('#uploadOk').show();
				$('#uploadFailed').hide();
				$('#uploadStatus').modal();
				reloadSetting();
			},
			error:function(status){
				// 向用户提示提交失败
				$('#uploadOk').hide();
				$('#uploadFailed').show();
				$('#uploadStatus').modal();
			}
		})
	}
	
}

function postSnList(){
	var sn_list = $('#sn_list').val();
	
	$.ajax({
		url: '/sn_list',
		type: 'post',
		dataType: 'text',
		headers: {
			"Content-Type": "text/plain; charset=utf-8"
		},
		contentType: 'text/plain; charset=utf-8',
		data: sn_list,
		success: function(data) {
			// 向用户提示提交成功
			$('#uploadOk').show();
			$('#uploadFailed').hide();
			$('#uploadStatus').modal();
			showSnList();
		},
		error:function(status){
			// 向用户提示提交失败
			$('#uploadOk').hide();
			$('#uploadFailed').show();
			$('#uploadStatus').modal();
		}
	})
}

function showSnList(){
	$.get("data/sn_list", function(data) {
		$("#sn_list").val(data);
	})
}

// === SNList 快速新增 ===

function updateSnListPreview() {
	var line = generateSnListLine();
	$('#plex_preview').text(line || ' ');
}

function generateSnListLine() {
	var snRaw = $('#plex_sn_input').val().trim();
	if (!snRaw) return '';

	// 從連結中提取 SN
	var snMatch = snRaw.match(/sn=(\d+)/i);
	var sn = snMatch ? snMatch[1] : snRaw.replace(/\D/g, '');
	if (!sn) return '';

	var mode = $('#plex_mode_select').val();
	var folder = $('#plex_folder_input').val().trim();
	var title = $('#plex_title_input').val().trim();
	var season = $('#plex_season_input').val().trim();
	var epOffset = $('#plex_ep_offset_input').val().trim();
	var comment = $('#plex_comment_input').val().trim();

	var line = sn + ' ' + mode;
	if (title) line += ' <' + title + '>';
	if (folder) line += ' {' + folder + '}';
	if (season) {
		var seasonStr = '(S' + String(season).padStart(2, '0');
		if (epOffset && parseInt(epOffset) > 0) seasonStr += '-' + epOffset;
		seasonStr += ')';
		line += ' ' + seasonStr;
	}
	if (comment) line += ' # ' + comment;

	return line;
}

function addSnListLine() {
	var line = generateSnListLine();
	if (!line) {
		alert('請輸入 SN 號碼或連結！');
		return;
	}
	var current = $('#sn_list').val().trim();
	if (current) {
		$('#sn_list').val(current + '\n' + line);
	} else {
		$('#sn_list').val(line);
	}
	// 清空表單
	$('#plex_sn_input').val('');
	$('#plex_folder_input').val('');
	$('#plex_title_input').val('');
	$('#plex_season_input').val('');
	$('#plex_ep_offset_input').val('');
	$('#plex_comment_input').val('');
	updateSnListPreview();
}

// 即時預覽：綁定輸入事件
$(function() {
	$('#plex_sn_input, #plex_mode_select, #plex_folder_input, #plex_title_input, #plex_season_input, #plex_ep_offset_input, #plex_comment_input')
		.on('input change', updateSnListPreview);
});

// === 排程資訊 ===

$(function() {
	$('#scheduleInfo').on('show.bs.modal', function() {
		loadSchedule();
	});
	$('#sub_sn, #sub_mode, #sub_folder, #sub_title, #sub_season, #sub_ep_offset, #sub_comment')
		.on('input change', updateSubscribePreview);
});

function loadSchedule() {
	$('#schedule_tbody').html('<tr><td colspan="6" class="text-center text-muted">載入中...</td></tr>');
	$('#schedule_error').hide();

	$.ajax({
		type: 'get',
		url: 'data/schedule',
		dataType: 'json',
		success: function(data) {
			if (data.error) {
				$('#schedule_error').text(data.error).show();
			}
			if (data.last_fetch) {
				$('#schedule_last_fetch').text(data.last_fetch);
			} else {
				$('#schedule_last_fetch').text('-');
			}
			renderScheduleTable(data.items || []);
		},
		error: function() {
			$('#schedule_tbody').html('<tr><td colspan="6" class="text-center text-danger">載入失敗</td></tr>');
		}
	});
}

function escapeHtml(str) {
	return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderScheduleTable(items) {
	var tbody = $('#schedule_tbody');
	tbody.empty();

	if (items.length === 0) {
		tbody.html('<tr><td colspan="6" class="text-center text-muted">無排程資料</td></tr>');
		return;
	}

	// 按星期和時間排序
	var dayOrder = ['週一', '週二', '週三', '週四', '週五', '週六', '週日'];
	items.sort(function(a, b) {
		var da = dayOrder.indexOf(a.day_name);
		var db = dayOrder.indexOf(b.day_name);
		if (da !== db) return da - db;
		return (a.time || '').localeCompare(b.time || '');
	});

	for (var i = 0; i < items.length; i++) {
		var item = items[i];
		var statusClass = item.in_sn_list ? 'text-success' : 'text-muted';
		var statusText = item.in_sn_list ? '已訂閱' : '未訂閱';
		var safeTitle = escapeHtml(item.title);
		var titleAttr = safeTitle.replace(/'/g, '&#39;');

		var actions = '';
		if (item.in_sn_list) {
			actions = '<button class="btn btn-sm btn-outline-danger mr-1" onclick="unsubscribeAnime(\'' + titleAttr + '\')">取消訂閱</button>' +
				'<button class="btn btn-sm btn-outline-primary" onclick="forceCheckAnime(\'' + titleAttr + '\')">立即檢查</button>';
		} else {
			actions = '<button class="btn btn-sm btn-success" onclick="showSubscribeForm(' + item.sn + ', \'' + titleAttr + '\')">訂閱</button>';
		}

		var row = '<tr' + (item.in_sn_list ? ' class="table-success"' : '') + '>' +
			'<td>' + item.day_name + '</td>' +
			'<td>' + (item.time || '-') + '</td>' +
			'<td>' + safeTitle + '</td>' +
			'<td>' + item.sn + '</td>' +
			'<td class="' + statusClass + '">' + statusText + '</td>' +
			'<td style="white-space:nowrap">' + actions + '</td>' +
			'</tr>';
		tbody.append(row);
	}
}

// --- 訂閱表單 ---

function showSubscribeForm(sn, title) {
	// 還原 HTML 實體
	var div = document.createElement('div');
	div.innerHTML = title;
	var cleanTitle = div.textContent || div.innerText || '';

	$('#sub_sn').val(sn);
	$('#sub_folder').val(cleanTitle);
	$('#sub_title').val('');
	$('#sub_season').val('');
	$('#sub_ep_offset').val('');
	$('#sub_comment').val('');
	$('#sub_sn_info').text('排程 SN: ' + sn + ' (最新集, 正在查詢第一集...)');
	$('#sub_mode').val('latest');
	updateSubscribePreview();
	$('#subscribe_form').slideDown();

	// 自動查詢第一集 SN
	fetchFirstSn();
}

function hideSubscribeForm() {
	$('#subscribe_form').slideUp();
}

function fetchFirstSn() {
	var sn = $('#sub_sn').val();
	if (!sn) return;

	$.ajax({
		type: 'get',
		url: 'data/anime_first_sn?sn=' + sn,
		dataType: 'json',
		success: function(data) {
			if (data.error) {
				$('#sub_sn_info').text('查詢失敗: ' + data.error);
			} else {
				$('#sub_sn').val(data.first_sn);
				$('#sub_sn_info').text('第一集 SN: ' + data.first_sn + ' (原查詢: ' + data.query_sn + ')');
				updateSubscribePreview();
			}
		},
		error: function() {
			$('#sub_sn_info').text('查詢失敗');
		}
	});
}

function updateSubscribePreview() {
	var sn = $('#sub_sn').val();
	if (!sn) { $('#sub_preview').html('&nbsp;'); return; }

	var mode = $('#sub_mode').val();
	var folder = $('#sub_folder').val().trim();
	var title = $('#sub_title').val().trim();
	var season = $('#sub_season').val().trim();
	var epOffset = $('#sub_ep_offset').val().trim();
	var comment = $('#sub_comment').val().trim();

	var line = sn + ' ' + mode;
	if (title) line += ' <' + title + '>';
	if (folder) line += ' {' + folder + '}';
	if (season) {
		var seasonStr = '(S' + String(season).padStart(2, '0');
		if (epOffset && parseInt(epOffset) > 0) seasonStr += '-' + epOffset;
		seasonStr += ')';
		line += ' ' + seasonStr;
	}
	if (comment) line += ' # ' + comment;

	$('#sub_preview').text(line);
}

function submitSubscribe() {
	var sn = $('#sub_sn').val();
	if (!sn) { alert('缺少 SN'); return; }

	var payload = {
		sn: sn,
		mode: $('#sub_mode').val(),
		folder_name: $('#sub_folder').val().trim(),
		clean_title: $('#sub_title').val().trim(),
		season: $('#sub_season').val().trim(),
		ep_offset: $('#sub_ep_offset').val().trim(),
		comment: $('#sub_comment').val().trim()
	};

	$.ajax({
		type: 'post',
		url: 'schedule/subscribe',
		data: JSON.stringify(payload),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.status === 200) {
				alert('訂閱成功！\n' + data.line);
				hideSubscribeForm();
				loadSchedule();
			} else {
				alert('訂閱失敗: ' + (data.error || '未知錯誤'));
			}
		},
		error: function() {
			alert('訂閱失敗: 網路錯誤');
		}
	});
}

// --- 取消訂閱 ---

function unsubscribeAnime(title) {
	// 還原 HTML 實體
	var div = document.createElement('div');
	div.innerHTML = title;
	var cleanTitle = div.textContent || div.innerText || '';

	if (!confirm('確定要取消訂閱「' + cleanTitle + '」嗎？')) return;

	$.ajax({
		type: 'post',
		url: 'schedule/unsubscribe',
		data: JSON.stringify({title: cleanTitle}),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.removed) {
				alert('已取消訂閱 (SN=' + data.sn + ')');
				loadSchedule();
			} else {
				alert('取消訂閱失敗: ' + (data.error || '未找到對應條目'));
			}
		},
		error: function() {
			alert('取消訂閱失敗: 網路錯誤');
		}
	});
}

// --- 立即檢查 ---

function forceCheckAnime(title) {
	// 還原 HTML 實體
	var div = document.createElement('div');
	div.innerHTML = title;
	var cleanTitle = div.textContent || div.innerText || '';

	$.ajax({
		type: 'post',
		url: 'schedule/force_check',
		data: JSON.stringify({title: cleanTitle}),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.status === 200) {
				alert('已排入立即檢查 (SN=' + data.sn + ')\n將在數秒內自動開始');
			} else {
				alert('操作失敗: ' + (data.error || '未知錯誤'));
			}
		},
		error: function() {
			alert('操作失敗: 網路錯誤');
		}
	});
}

// === 任務監控浮動面板 ===

var monitorInterval = null;
var logInterval = null;
var monitorKnownTasks = {};
var lastLogLine = '';

$(function() {
	$('#toggleMonitor').on('click', function(e) {
		e.preventDefault();
		var panel = $('#monitorPanel');
		if (panel.is(':visible')) {
			closeMonitorPanel();
		} else {
			openMonitorPanel();
		}
	});

	$('#closeMonitor').on('click', function() {
		closeMonitorPanel();
	});
});

function openMonitorPanel() {
	$('#monitorPanel').show();
	// 立即載入一次
	fetchMonitorTasks();
	fetchMonitorLogs();
	// 開始輪詢: 任務進度 1 秒, 日誌 2 秒
	monitorInterval = setInterval(fetchMonitorTasks, 1000);
	logInterval = setInterval(fetchMonitorLogs, 2000);
}

function closeMonitorPanel() {
	$('#monitorPanel').hide();
	if (monitorInterval) { clearInterval(monitorInterval); monitorInterval = null; }
	if (logInterval) { clearInterval(logInterval); logInterval = null; }
}

function fetchMonitorTasks() {
	$.get('data/tasks_progress', function(data) {
		if (typeof data === 'string') {
			try { data = JSON.parse(data); } catch(e) { return; }
		}

		var container = $('#monitorTasks');
		var hasTask = false;

		for (var sn in data) {
			hasTask = true;
			var task = data[sn];
			var pct = Math.round(task.rate || 0);
			var existing = container.find('#mt_' + sn);

			if (existing.length > 0) {
				// 更新
				existing.find('.monitor-task-name').text(task.filename || 'SN=' + sn);
				existing.find('.monitor-task-fill').css('width', pct + '%');
				existing.find('.mt-pct').text(pct + '%');
				existing.find('.mt-status').text(task.status || '');
			} else {
				// 新增
				var html = '<div class="monitor-task" id="mt_' + sn + '">'
					+ '<div class="monitor-task-name">' + escapeHtml(task.filename || 'SN=' + sn) + '</div>'
					+ '<div class="monitor-task-bar"><div class="monitor-task-fill" style="width:' + pct + '%"></div></div>'
					+ '<div class="monitor-task-info"><span class="mt-status">' + escapeHtml(task.status || '') + '</span><span class="mt-pct">' + pct + '%</span></div>'
					+ '</div>';
				container.append(html);
			}
			monitorKnownTasks[sn] = true;
		}

		// 移除已完成的
		for (var sn in monitorKnownTasks) {
			if (!(sn in data)) {
				container.find('#mt_' + sn).remove();
				delete monitorKnownTasks[sn];
			}
		}

		if (hasTask) {
			$('#monitorNoTask').hide();
		} else {
			$('#monitorNoTask').show();
		}
	});
}

function fetchMonitorLogs() {
	$.get('data/recent_logs?n=80', function(data) {
		if (typeof data === 'string') {
			try { data = JSON.parse(data); } catch(e) { return; }
		}
		var lines = data.lines || [];
		// 只在日誌有變化時更新 DOM (比對最後一行)
		var currentLast = lines.length > 0 ? lines[lines.length - 1] : '';
		if (currentLast === lastLogLine && lines.length > 0) return;
		lastLogLine = currentLast;

		var container = $('#monitorLogs');
		var wasAtBottom = container[0].scrollHeight - container[0].scrollTop - container[0].clientHeight < 30;

		var html = '';
		for (var i = 0; i < lines.length; i++) {
			var line = lines[i];
			var cls = 'monitor-log-line';
			// 簡易分類: 含「失敗」「ERROR」「錯誤」→ 紅色, 含「完成」「成功」→ 綠色
			if (/失[敗败]|ERROR|錯誤|错误/.test(line)) {
				cls += ' log-error';
			} else if (/完成|成功|Refresh/.test(line)) {
				cls += ' log-success';
			}
			html += '<div class="' + cls + '">' + escapeHtml(line) + '</div>';
		}
		container.html(html);

		// 自動捲動到底部 (除非使用者正在往上捲)
		if (wasAtBottom) {
			container[0].scrollTop = container[0].scrollHeight;
		}
	});
}