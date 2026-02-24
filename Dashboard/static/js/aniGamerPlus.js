// aniGamerPlus Dashboard - 主要前端邏輯
// 所有 Bootstrap 依賴已移除，改用原生 DOM + jQuery AJAX

var dataArrays; // 使用者設定 JSON
var proxy_protocol;
var proxy_ip;
var proxy_port;
var proxy_user = '';
var proxy_passwd = '';
id_list.push('proxy_protocol', 'proxy_ip', 'proxy_port', 'proxy_user', 'proxy_passwd');

// === 初始化：載入設定 ===
$.ajax({
	type: 'get',
	url: 'data/config.json',
	dataType: 'json',
	async: true,
	success: function(data) {
		dataArrays = data;
		parseProxy(data.proxy);
		$(function() { renderJson(); });
	}
});

showSnList();

// === Modal 系統 ===
function openModal(id) {
	document.getElementById(id).classList.remove('hidden');
}
function closeModal(id) {
	document.getElementById(id).classList.add('hidden');
}
function openScheduleModal() {
	openModal('scheduleModal');
	loadSchedule();
}

// === 主題切換 ===
function cycleTheme() {
	var saved = localStorage.getItem('theme') || 'auto';
	var next = saved === 'dark' ? 'light' : saved === 'light' ? 'auto' : 'dark';
	localStorage.setItem('theme', next);
	applyTheme(next);
	updateThemeIcon();
}

function applyTheme(mode) {
	if (mode === 'light' || (mode === 'auto' && window.matchMedia('(prefers-color-scheme: light)').matches)) {
		document.documentElement.classList.add('light');
	} else {
		document.documentElement.classList.remove('light');
	}
}

function updateThemeIcon() {
	var icon = document.getElementById('themeIcon');
	if (!icon) return;
	var saved = localStorage.getItem('theme') || 'auto';
	icon.className = 'fas ' + (saved === 'light' ? 'fa-sun' : saved === 'dark' ? 'fa-moon' : 'fa-adjust');
}

$(function() { updateThemeIcon(); });
$(function() { initManualLinkListener(); });

// === 導航列手機版 toggle ===
$(function() {
	$('#navToggle').on('click', function() {
		$('#navMenu').toggleClass('hidden');
	});
});

// === 代理設定解析 ===
function parseProxy(proxy) {
	proxy_protocol = proxy.replace(/:\/\/.*/i, '').toUpperCase();
	if (/.*@.*/.test(proxy)) {
		proxy_user = /:\/\/.*?:/g.exec(proxy)[0].replace(/:(\/\/)?/g, '');
		proxy_passwd = /:.*@/.exec(proxy)[0].replace(proxy_user, '')
			.replace(/(:\/\/:)?@?/g, '');
		proxy = proxy.replace(proxy_user + ':' + proxy_passwd + '@', '');
	}
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

// === 設定表單渲染 ===
function renderJson() {
	for (var id of id_list) {
		if (id === 'proxy') continue; // 代理設定已拆解
		var el = document.getElementById(id);
		if (!el) continue;
		var idType = el.type;
		switch (idType) {
			case 'text':
			case 'number':
			case 'password':
				if (id === 'multi-thread')
					$('#manual_thread_limit').val(dataArrays[id]);
				$('#' + id.replace(/([:.])/g, '\\$1')).val(dataArrays[id]);
				break;
			case 'checkbox':
				el.checked = dataArrays[id];
				break;
			case 'select-one':
				if (id === 'proxy_protocol') {
					el.value = dataArrays[id].toUpperCase();
				} else if (id === 'download_resolution') {
					// 值為 '1080' 需對應 '1080P'
					var resVal = String(dataArrays[id]);
					if (!resVal.endsWith('P')) resVal += 'P';
					el.value = resVal;
				} else if (id === 'default_download_mode') {
					el.value = dataArrays[id];
				} else {
					el.value = dataArrays[id];
				}
				break;
		}
	}
}

function reloadSetting() {
	readJson();
	renderJson();
}

function readJson() {
	$.getJSON('data/config.json', function(data) {
		dataArrays = data;
		parseProxy(data.proxy); // 解析代理設定
	});
}

// === 讀取表單並儲存 ===
function readSettings() {
	for (var id of id_list) {
		if (id === 'proxy') continue; // 代理設定已拆解

		var el = document.getElementById(id);
		if (!el) continue;
		var idType = el.type;
		switch (idType) {
			case 'number':
				dataArrays[id] = Number($('#' + id.replace(/([:.])/g, '\\$1')).val());
				break;
			case 'text':
			case 'password':
				dataArrays[id] = $('#' + id.replace(/([:.])/g, '\\$1')).val();
				break;
			case 'checkbox':
				dataArrays[id] = el.checked;
				break;
			case 'select-one':
				if (id === 'proxy_protocol') {
					dataArrays[id] = el.value.toLowerCase();
				} else if (id === 'download_resolution') {
					dataArrays[id] = el.value.replace('P', '');
				} else {
					dataArrays[id] = el.value;
				}
				break;
		}
	}

	// 合併代理設定
	var ip_port = dataArrays['proxy_ip'] + ':' + dataArrays['proxy_port'];
	var protocol = dataArrays['proxy_protocol'] + '://';
	if (!dataArrays['proxy_user'] || !dataArrays['proxy_passwd'] ||
		dataArrays['proxy_user'].length * dataArrays['proxy_passwd'].length === 0) {
		// 若無使用者密碼
		dataArrays['proxy'] = protocol + ip_port;
	} else {
		var user_pw = dataArrays['proxy_user'] + ':' + dataArrays['proxy_passwd'] + '@';
		dataArrays['proxy'] = protocol + user_pw + ip_port;
	}

	$.ajax({
		url: '/uploadConfig',
		type: 'post',
		dataType: 'json',
		contentType: 'application/json; charset=utf-8',
		data: JSON.stringify(dataArrays),
		success: function() {
			// 向使用者提示儲存成功
			$('#uploadOk').show();
			$('#uploadFailed').hide();
			openModal('uploadStatusModal');
			reloadSetting();
		},
		error: function() {
			// 向使用者提示儲存失敗
			$('#uploadOk').hide();
			$('#uploadFailed').show();
			openModal('uploadStatusModal');
		}
	});
}

function getUA() {
	$('#ua').val(navigator.userAgent);
	alert('已取得當前瀏覽器 UA');
}

// === 手動任務 ===
var _manualPreviewData = null;  // 快取查詢結果 {title, episode, default_filename, suggest}
var _manualPreviewTimer = null; // debounce timer

function _extractSn(raw) {
	return raw.replace(/(https:\/\/)?ani\.gamer\.com\.tw\/animeVideo\.php\?sn=/i, '').replace(/\D/g, '');
}

function initManualLinkListener() {
	$('#manual_link').on('input', function() {
		clearTimeout(_manualPreviewTimer);
		_manualPreviewTimer = setTimeout(function() {
			fetchManualPreview();
		}, 500);
	});
	$('#manual_resolution').on('change', function() { updateManualPreview(); });
}

function fetchManualPreview() {
	var sn = _extractSn($('#manual_link').val());
	if (!sn) {
		_manualPreviewData = null;
		$('#manual_preview').html('&nbsp;');
		return;
	}
	// SN 變更時重置命名欄位和 toggle
	$('#manual_plex_toggle').prop('checked', false);
	$('#manual_plex_folder').val('');
	$('#manual_plex_title').val('');
	$('#manual_plex_season').val('');
	$('#manual_plex_offset').val('');
	_manualPreviewData = null;
	$('#manual_preview').text('查詢中...').removeClass('text-green-400').addClass('text-gray-500');
	$.ajax({
		type: 'get',
		url: 'data/manual_preview?sn=' + sn,
		dataType: 'json',
		success: function(data) {
			if (data.error) {
				$('#manual_preview').text('查詢失敗: ' + data.error).removeClass('text-gray-500').addClass('text-red-400');
				_manualPreviewData = null;
				return;
			}
			_manualPreviewData = data;
			$('#manual_preview').removeClass('text-gray-500 text-red-400').addClass('text-green-400');
			// 如果 toggle 已開啟，自動預填
			if (document.getElementById('manual_plex_toggle').checked) {
				_applyManualSuggest();
			}
			updateManualPreview();
		},
		error: function() {
			$('#manual_preview').text('查詢失敗').removeClass('text-gray-500').addClass('text-red-400');
			_manualPreviewData = null;
		}
	});
}

function updateManualPreview() {
	if (!_manualPreviewData) {
		$('#manual_preview').html('&nbsp;');
		return;
	}
	var folder = $('#manual_plex_folder').val().trim();
	if (!folder) {
		// 無命名設定 → 顯示預設檔名
		$('#manual_preview').text(_manualPreviewData.default_filename);
		return;
	}
	// 有命名設定 → 計算 Plex 格式預覽
	var title = $('#manual_plex_title').val().trim() || folder;
	var season = $('#manual_plex_season').val();
	var offset = parseInt($('#manual_plex_offset').val()) || 0;
	var episode = _manualPreviewData.episode;
	// 季數: 空值時使用 suggest 的季數
	var seasonNum = (season !== '' && season !== null) ? parseInt(season) : (_manualPreviewData.suggest ? _manualPreviewData.suggest.season_num : 1);
	if (isNaN(seasonNum)) seasonNum = 1;
	// 計算 Plex 檔名
	var ext = 'mp4';
	var epNum = parseInt(episode);
	var filename;
	if (isNaN(epNum)) {
		// 非數字集數 (特別篇/電影等) → S00
		var nums = episode.match(/\d+/);
		var epStr = nums ? String(nums[0]).padStart(2, '0') : '01';
		filename = title + ' S00E' + epStr + '.' + ext;
	} else {
		if (offset > 0 && epNum > offset) {
			epNum = epNum - offset;
		}
		epNum = Math.max(epNum, 1);
		var seasonStr = String(seasonNum).padStart(2, '0');
		var epStr = String(epNum).padStart(2, '0');
		filename = title + ' S' + seasonStr + 'E' + epStr + '.' + ext;
	}
	$('#manual_preview').text(folder + '/' + filename);
}

function _applyManualSuggest() {
	if (!_manualPreviewData || !_manualPreviewData.suggest) return;
	var s = _manualPreviewData.suggest;
	// 強制覆寫所有欄位
	$('#manual_plex_folder').val(s.folder_name || '');
	$('#manual_plex_title').val(s.clean_title || '');
	$('#manual_plex_season').val(s.season_num !== undefined ? s.season_num : '');
	$('#manual_plex_offset').val(s.ep_offset || 0);
}

function toggleManualPlex() {
	if (document.getElementById('manual_plex_toggle').checked) {
		// ON: 預填
		if (_manualPreviewData) {
			_applyManualSuggest();
			updateManualPreview();
		} else {
			// 尚未查詢，觸發查詢
			fetchManualPreview();
		}
	} else {
		// OFF: 清空命名欄位
		$('#manual_plex_folder').val('');
		$('#manual_plex_title').val('');
		$('#manual_plex_season').val('');
		$('#manual_plex_offset').val('');
		updateManualPreview();
	}
}

function readManualConfig() {
	var link = $('#manual_link').val();
	if (link.length === 0) {
		alert('請輸入影片連結！');
		return;
	}

	var sn = _extractSn(link);
	var manualData = {
		sn: sn,
		mode: $('#manual_mode').val(),
		resolution: $('#manual_resolution').val().replace('P', ''),
		classify: document.getElementById('manual_classify').checked,
		thread: $('#manual_thread_limit').val(),
		danmu: document.getElementById('manual_danmu').checked,
		plex_info: null
	};

	// 如果有填入資料夾名，構建 plex_info
	var folder = $('#manual_plex_folder').val().trim();
	if (folder) {
		var title = $('#manual_plex_title').val().trim() || folder;
		var season = $('#manual_plex_season').val();
		var seasonNum = (season !== '' && season !== null) ? parseInt(season) : -1;
		var offset = parseInt($('#manual_plex_offset').val()) || 0;
		manualData.plex_info = {
			folder_name: folder,
			clean_title: title,
			season_num: isNaN(seasonNum) ? -1 : seasonNum,
			ep_offset: offset
		};
	}

	$.ajax({
		url: '/manualTask',
		type: 'post',
		dataType: 'json',
		contentType: 'application/json; charset=utf-8',
		data: JSON.stringify(manualData),
		success: function() {
			$('#uploadOk').show();
			$('#uploadFailed').hide();
			openModal('uploadStatusModal');
		},
		error: function() {
			$('#uploadOk').hide();
			$('#uploadFailed').show();
			openModal('uploadStatusModal');
		}
	});
}

// === sn_list ===
function postSnList() {
	var sn_list = $('#sn_list').val();
	$.ajax({
		url: '/sn_list',
		type: 'post',
		dataType: 'text',
		contentType: 'text/plain; charset=utf-8',
		data: sn_list,
		success: function() {
			$('#uploadOk').show();
			$('#uploadFailed').hide();
			openModal('uploadStatusModal');
			showSnList();
		},
		error: function() {
			$('#uploadOk').hide();
			$('#uploadFailed').show();
			openModal('uploadStatusModal');
		}
	});
}

function showSnList() {
	$.get('data/sn_list', function(data) {
		$('#sn_list').val(data);
	});
}

// === SNList 快速新增 ===
function updateSnListPreview() {
	var line = generateSnListLine();
	$('#plex_preview').text(line || ' ');
}

function generateSnListLine() {
	var snRaw = $('#plex_sn_input').val().trim();
	if (!snRaw) return '';

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

function fetchFirstSnForSnList() {
	var raw = $('#plex_sn_input').val().trim();
	var snMatch = raw.match(/sn=(\d+)/i);
	var sn = snMatch ? snMatch[1] : raw.replace(/\D/g, '');
	if (!sn) { $('#plex_sn_info').text('請先輸入 SN'); return; }

	$('#plex_sn_info').text('正在查詢第一集...').removeClass('text-red-400').addClass('text-gray-500');
	$.ajax({
		type: 'get',
		url: 'data/anime_first_sn?sn=' + sn,
		dataType: 'json',
		success: function(data) {
			if (data.error) {
				$('#plex_sn_info').text('查詢失敗：' + data.error).removeClass('text-gray-500').addClass('text-red-400');
			} else {
				$('#plex_sn_input').val(data.first_sn);
				$('#plex_sn_info').text('第一集 SN: ' + data.first_sn + (data.title ? ' — ' + data.title : '')).removeClass('text-red-400').addClass('text-gray-500');
				if (data.title && !$('#plex_folder_input').val().trim()) {
					$('#plex_folder_input').val(data.title);
				}
				updateSnListPreview();
			}
		},
		error: function(xhr) {
			var msg = '查詢失敗';
			try { var r = JSON.parse(xhr.responseText); if (r.error) msg += '：' + r.error; } catch(e) {}
			$('#plex_sn_info').text(msg).removeClass('text-gray-500').addClass('text-red-400');
		}
	});
}

function addSnListLine() {
	var line = generateSnListLine();
	if (!line) {
		alert('請輸入 SN 號碼或連結！');
		return;
	}
	var current = $('#sn_list').val().trim();
	$('#sn_list').val(current ? current + '\n' + line : line);
	// 清空表單
	$('#plex_sn_input, #plex_folder_input, #plex_title_input, #plex_season_input, #plex_ep_offset_input, #plex_comment_input').val('');
	updateSnListPreview();
}

// 即時預覽
$(function() {
	$('#plex_sn_input, #plex_mode_select, #plex_folder_input, #plex_title_input, #plex_season_input, #plex_ep_offset_input, #plex_comment_input')
		.on('input change', updateSnListPreview);
});

// === 排程資訊 ===
$(function() {
	$('#sub_sn, #sub_mode, #sub_folder, #sub_title, #sub_season, #sub_ep_offset, #sub_comment')
		.on('input change', updateSubscribePreview);
});

var _bahaScheduleLoaded = false;

function loadSchedule(force) {
	// Modal 入口：預設顯示「我的排程」tab
	switchScheduleTab('my');
	loadTimetable();
	// 巴哈排程延遲到切 tab 時載入
	if (force) {
		_bahaScheduleLoaded = false;
		loadBahaSchedule(true);
		switchScheduleTab('baha');
	}
}

function switchScheduleTab(tab) {
	var $my = $('#schedPanel_my');
	var $baha = $('#schedPanel_baha');
	var $tabMy = $('#schedTab_my');
	var $tabBaha = $('#schedTab_baha');
	if (tab === 'my') {
		$baha.hide();
		$my.show();
		$tabMy.removeClass('bg-gray-700 text-gray-300').addClass('bg-cyan-600 text-white');
		$tabBaha.removeClass('bg-cyan-600 text-white').addClass('bg-gray-700 text-gray-300');
	} else {
		$my.hide();
		$baha.show();
		$tabBaha.removeClass('bg-gray-700 text-gray-300').addClass('bg-cyan-600 text-white');
		$tabMy.removeClass('bg-cyan-600 text-white').addClass('bg-gray-700 text-gray-300');
		if (!_bahaScheduleLoaded) {
			loadBahaSchedule(false);
		}
	}
}

function loadBahaSchedule(force) {
	hideSubscribeForm();
	$('#schedule_tbody').html('<tr><td colspan="5" class="px-3 py-4 text-center text-gray-500">載入中...</td></tr>');
	$('#schedule_error').addClass('hidden');
	if (force) {
		$('#btn_force_fetch').prop('disabled', true).html('<i class="fas fa-spinner fa-spin text-xs"></i> 抓取中...').removeClass('bg-blue-600 hover:bg-blue-500').addClass('bg-gray-600 cursor-not-allowed');
	}

	$.ajax({
		type: 'get',
		url: 'data/schedule' + (force ? '?force=1' : ''),
		dataType: 'json',
		success: function(data) {
			_bahaScheduleLoaded = true;
			if (data.error) {
				$('#schedule_error').text(data.error).removeClass('hidden');
			}
			$('#schedule_last_fetch').text(data.last_fetch || '-');
			renderScheduleTable(data.items || []);
		},
		error: function() {
			$('#schedule_tbody').html('<tr><td colspan="5" class="px-3 py-4 text-center text-red-400">載入失敗</td></tr>');
		},
		complete: function() {
			if (force) {
				$('#btn_force_fetch').prop('disabled', false).html('<i class="fas fa-sync-alt text-xs"></i> 從巴哈重新抓取').removeClass('bg-gray-600 cursor-not-allowed').addClass('bg-blue-600 hover:bg-blue-500');
			}
		}
	});
	// 強制抓取時也刷新 timetable（因為會觸發主迴圈重建）
	if (force) {
		setTimeout(function() { loadTimetable(); }, 2000);
	}
}

// === 我的排程表 ===
function loadTimetable() {
	$('#timetable_container').html('<div class="text-gray-500 text-center py-3 text-sm">載入中...</div>');
	$.ajax({
		type: 'get',
		url: 'data/schedule/timetable',
		dataType: 'json',
		success: function(data) {
			renderTimetable(data.items || []);
		},
		error: function() {
			$('#timetable_container').html('<div class="text-red-400 text-center py-3 text-sm">載入失敗</div>');
		}
	});
}

function renderTimetable(items) {
	var container = $('#timetable_container');
	container.empty();

	if (items.length === 0) {
		container.html('<div class="text-gray-500 text-center py-3 text-sm">排程模式未啟用或無匹配項目</div>');
		return;
	}

	var dayOrder = ['週一', '週二', '週三', '週四', '週五', '週六', '週日'];
	var jsDay = new Date().getDay();
	var todayIdx = jsDay === 0 ? 6 : jsDay - 1;

	// 分成今天 / 其他
	var todayItems = [];
	var otherItems = [];
	for (var i = 0; i < items.length; i++) {
		if (items[i].day === todayIdx) {
			todayItems.push(items[i]);
		} else {
			otherItems.push(items[i]);
		}
	}

	// 排序
	todayItems.sort(function(a, b) { return (a.trigger_time || '').localeCompare(b.trigger_time || ''); });
	otherItems.sort(function(a, b) {
		if (a.day !== b.day) return a.day - b.day;
		return (a.trigger_time || '').localeCompare(b.trigger_time || '');
	});

	// 今天的排程
	if (todayItems.length > 0) {
		container.append(
			'<div class="text-sm text-cyan-400 font-semibold mb-1 px-1">今天 (' + dayOrder[todayIdx] + ') — ' + todayItems.length + ' 項</div>'
		);
		var table = $('<table class="w-full text-sm mb-3"><thead><tr class="bg-gray-800 text-gray-400 text-left">' +
			'<th class="px-3 py-2 rounded-tl-md">番劇名</th>' +
			'<th class="px-3 py-2">播出</th>' +
			'<th class="px-3 py-2">觸發</th>' +
			'<th class="px-3 py-2">狀態</th>' +
			'<th class="px-3 py-2 rounded-tr-md">操作</th>' +
			'</tr></thead><tbody class="divide-y divide-gray-800"></tbody></table>');
		var tbody = table.find('tbody');
		for (var j = 0; j < todayItems.length; j++) {
			tbody.append(_buildTimetableRow(todayItems[j], true));
		}
		container.append(table);
	}

	// 其他日子
	if (otherItems.length > 0) {
		container.append(
			'<div class="text-sm text-gray-400 font-semibold mb-1 px-1 ' + (todayItems.length > 0 ? 'mt-3' : '') + '">其他日子 — ' + otherItems.length + ' 項</div>'
		);
		var table2 = $('<table class="w-full text-sm"><thead><tr class="bg-gray-800 text-gray-400 text-left">' +
			'<th class="px-3 py-2 rounded-tl-md">番劇名</th>' +
			'<th class="px-3 py-2">播出日</th>' +
			'<th class="px-3 py-2">播出</th>' +
			'<th class="px-3 py-2">觸發</th>' +
			'<th class="px-3 py-2 rounded-tr-md">操作</th>' +
			'</tr></thead><tbody class="divide-y divide-gray-800"></tbody></table>');
		var tbody2 = table2.find('tbody');
		for (var k = 0; k < otherItems.length; k++) {
			tbody2.append(_buildTimetableRow(otherItems[k], false));
		}
		container.append(table2);
	}
}

function _buildTimetableRow(item, isToday) {
	var safeTitle = escapeHtml(item.title);
	var pinIcon = item.pinned
		? ' <span class="text-yellow-400 cursor-help" title="已手動覆寫，本週不會被自動刷新覆蓋"><i class="fas fa-thumbtack"></i></span>'
		: '';

	// 狀態 badge
	var statusHtml = '';
	if (isToday) {
		if (item.status === 'triggered') {
			statusHtml = '<span class="text-green-400"><i class="fas fa-check-circle"></i> 已觸發</span>';
		} else if (item.status === 'retrying') {
			statusHtml = '<span class="text-yellow-400"><i class="fas fa-redo"></i> 重試中 (' + item.retry_attempt + ')</span>';
		} else {
			statusHtml = '<span class="text-gray-400"><i class="far fa-clock"></i> 待觸發</span>';
		}
	}

	// 操作按鈕
	var actions = '<button class="text-gray-400 hover:text-cyan-400 transition-colors" onclick="editTimetableItem(' + item.sn + ', this)" title="編輯觸發時間"><i class="fas fa-edit"></i></button>';
	if (isToday && item.status !== 'triggered') {
		actions += ' <button class="text-gray-400 hover:text-green-400 transition-colors ml-1" onclick="forceCheckFromTimetable(' + item.sn + ')" title="立即檢查"><i class="fas fa-play"></i></button>';
	}
	if (item.pinned) {
		actions += ' <button class="text-yellow-400 hover:text-red-400 transition-colors ml-1" onclick="clearTimetableOverride(' + item.sn + ')" title="取消覆寫，恢復自動排程"><i class="fas fa-times-circle"></i></button>';
	}

	var dataAttr = 'data-sn="' + item.sn + '" data-day="' + item.day + '" data-hour="' + item.trigger_hour + '" data-min="' + item.trigger_minute + '" data-sec="' + item.trigger_second + '"';

	if (isToday) {
		return '<tr class="hover:bg-gray-800/50" id="tt_row_' + item.sn + '" ' + dataAttr + '>' +
			'<td class="px-3 py-2 text-gray-200">' + safeTitle + '</td>' +
			'<td class="px-3 py-2 text-gray-400">' + (item.time || '-') + '</td>' +
			'<td class="px-3 py-2 text-gray-200 tt-trigger-cell">' + (item.trigger_time || '-') + pinIcon + '</td>' +
			'<td class="px-3 py-2">' + statusHtml + '</td>' +
			'<td class="px-3 py-2 whitespace-nowrap">' + actions + '</td>' +
			'</tr>';
	} else {
		var dayNames = ['週一', '週二', '週三', '週四', '週五', '週六', '週日'];
		return '<tr class="hover:bg-gray-800/50" id="tt_row_' + item.sn + '" ' + dataAttr + '>' +
			'<td class="px-3 py-2 text-gray-300">' + safeTitle + '</td>' +
			'<td class="px-3 py-2 text-gray-500">' + dayNames[item.day] + '</td>' +
			'<td class="px-3 py-2 text-gray-400">' + (item.time || '-') + '</td>' +
			'<td class="px-3 py-2 text-gray-300 tt-trigger-cell">' + (item.trigger_time || '-') + pinIcon + '</td>' +
			'<td class="px-3 py-2 whitespace-nowrap">' + actions + '</td>' +
			'</tr>';
	}
}

function editTimetableItem(sn, btnEl) {
	var $row = $('#tt_row_' + sn);
	if (!$row.length) return;

	var $triggerCell = $row.find('.tt-trigger-cell');
	// 從 data attribute 讀取當前值
	var day = parseInt($row.attr('data-day')) || 0;
	var hour = parseInt($row.attr('data-hour')) || 0;
	var minute = parseInt($row.attr('data-min')) || 0;
	var second = parseInt($row.attr('data-sec')) || 0;

	$triggerCell.data('original-html', $triggerCell.html());

	var daySelect = '<select class="tt-edit-day bg-gray-800 text-gray-100 border border-gray-600 rounded text-xs px-1 py-0.5 w-12">';
	var dayNames = ['一', '二', '三', '四', '五', '六', '日'];
	for (var d = 0; d < 7; d++) {
		var sel = d === day ? ' selected' : '';
		daySelect += '<option value="' + d + '"' + sel + '>' + dayNames[d] + '</option>';
	}
	daySelect += '</select>';

	$triggerCell.html(
		daySelect +
		' <input type="number" min="0" max="23" value="' + hour + '" class="tt-edit-hour bg-gray-800 text-gray-100 border border-gray-600 rounded text-xs px-1 py-0.5 w-10 text-center">' +
		':<input type="number" min="0" max="59" value="' + minute + '" class="tt-edit-min bg-gray-800 text-gray-100 border border-gray-600 rounded text-xs px-1 py-0.5 w-10 text-center">' +
		':<input type="number" min="0" max="59" value="' + second + '" class="tt-edit-sec bg-gray-800 text-gray-100 border border-gray-600 rounded text-xs px-1 py-0.5 w-10 text-center">' +
		' <button class="text-green-400 hover:text-green-300 text-xs ml-1" onclick="saveTimetableOverride(' + sn + ')"><i class="fas fa-check"></i></button>' +
		' <button class="text-gray-400 hover:text-red-400 text-xs" onclick="cancelTimetableEdit(' + sn + ')"><i class="fas fa-times"></i></button>'
	);
}

function cancelTimetableEdit(sn) {
	var $row = $('#tt_row_' + sn);
	var $triggerCell = $row.find('.tt-trigger-cell');
	var originalHtml = $triggerCell.data('original-html');
	if (originalHtml) {
		$triggerCell.html(originalHtml);
	}
}

function saveTimetableOverride(sn) {
	var $row = $('#tt_row_' + sn);
	var $triggerCell = $row.find('.tt-trigger-cell');
	var day = parseInt($triggerCell.find('.tt-edit-day').val()) || 0;
	var hour = parseInt($triggerCell.find('.tt-edit-hour').val()) || 0;
	var minute = parseInt($triggerCell.find('.tt-edit-min').val()) || 0;
	var second = parseInt($triggerCell.find('.tt-edit-sec').val()) || 0;

	$.ajax({
		type: 'post',
		url: 'schedule/override',
		data: JSON.stringify({ sn: sn, day: day, hour: hour, minute: minute, second: second }),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.status === 200) {
				// 等主迴圈處理後再刷新
				setTimeout(function() { loadTimetable(); }, 1500);
			} else {
				alert('覆寫失敗：' + (data.error || '未知錯誤'));
			}
		},
		error: function() { alert('覆寫失敗：網路錯誤'); }
	});
}

function clearTimetableOverride(sn) {
	if (!confirm('確定取消覆寫？將恢復使用巴哈排程的自動時間。')) return;
	$.ajax({
		type: 'post',
		url: 'schedule/override/clear',
		data: JSON.stringify({ sn: sn }),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.status === 200) {
				setTimeout(function() { loadTimetable(); }, 1500);
			} else {
				alert('操作失敗：' + (data.error || '未知錯誤'));
			}
		},
		error: function() { alert('操作失敗：網路錯誤'); }
	});
}

function forceCheckFromTimetable(sn) {
	$.ajax({
		type: 'post',
		url: 'schedule/force_check_sn',
		data: JSON.stringify({ sn: sn }),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.status === 200) {
				alert('已排入立即檢查 (SN=' + data.sn + ')');
			} else {
				alert('操作失敗：' + (data.error || '未知錯誤'));
			}
		},
		error: function() { alert('操作失敗：網路錯誤'); }
	});
}

function escapeHtml(str) {
	return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderScheduleTable(items) {
	var tbody = $('#schedule_tbody');
	tbody.empty();

	if (items.length === 0) {
		tbody.html('<tr><td colspan="5" class="px-3 py-4 text-center text-gray-500">無排程資料</td></tr>');
		return;
	}

	var dayOrder = ['週一', '週二', '週三', '週四', '週五', '週六', '週日'];
	// 取得今天星期幾 (0=週一 ~ 6=週日)
	var jsDay = new Date().getDay(); // 0=Sun
	var todayIdx = jsDay === 0 ? 6 : jsDay - 1;

	items.sort(function(a, b) {
		var da = dayOrder.indexOf(a.day_name);
		var db = dayOrder.indexOf(b.day_name);
		if (da !== db) return da - db;
		return (a.time || '').localeCompare(b.time || '');
	});

	// 依星期分組
	var grouped = {};
	for (var i = 0; i < items.length; i++) {
		var day = items[i].day_name;
		if (!grouped[day]) grouped[day] = [];
		grouped[day].push(items[i]);
	}

	var todayHeaderId = '';
	var isFirstDay = true;
	for (var d = 0; d < dayOrder.length; d++) {
		var dayName = dayOrder[d];
		var dayItems = grouped[dayName];
		if (!dayItems) continue;

		var isToday = d === todayIdx;
		var headerId = 'schedDay_' + d;
		if (isToday) todayHeaderId = headerId;

		// 星期間隔列（非第一個星期前加空白間隔）
		if (!isFirstDay) {
			tbody.append('<tr class="schedule-day-spacer"><td colspan="5" class="py-2 bg-transparent"></td></tr>');
		}
		isFirstDay = false;

		// 星期標題列
		var headerClass = isToday
			? 'bg-cyan-900/30 text-cyan-400 font-bold border-l-[3px] border-cyan-400'
			: 'bg-gray-800/60 text-gray-300 font-semibold';
		var todayBadge = isToday ? ' <span class="text-xs font-normal ml-1 opacity-70">（今天）</span>' : '';
		tbody.append(
			'<tr id="' + headerId + '" class="schedule-day-header">' +
			'<td colspan="5" class="px-3 py-2.5 ' + headerClass + '">' +
			dayName + todayBadge +
			' <span class="text-xs text-gray-500 font-normal ml-2">' + dayItems.length + ' 部</span>' +
			'</td></tr>'
		);

		// 該日的番劇列表
		for (var j = 0; j < dayItems.length; j++) {
			var item = dayItems[j];
			var statusClass = item.in_sn_list ? 'text-green-400' : 'text-gray-500';
			var statusText = item.in_sn_list ? '已訂閱' : '未訂閱';
			var safeTitle = escapeHtml(item.title);
			var titleAttr = safeTitle.replace(/'/g, '&#39;');

			var actions = '';
			if (item.in_sn_list) {
				actions =
					'<button class="bg-red-700 hover:bg-red-600 text-white text-xs rounded px-2 py-1 mr-1 transition-colors" onclick="unsubscribeAnime(\'' + titleAttr + '\')">取消訂閱</button>' +
					'<button class="bg-blue-700 hover:bg-blue-600 text-white text-xs rounded px-2 py-1 transition-colors" onclick="forceCheckAnime(\'' + titleAttr + '\')">立即檢查</button>';
			} else {
				actions =
					'<button class="bg-cyan-700 hover:bg-cyan-600 text-white text-xs rounded px-2 py-1 transition-colors" onclick="showSubscribeForm(' + item.sn + ', \'' + titleAttr + '\', this)">訂閱</button>';
			}

			// 動畫瘋連結
			var animeLink = '<a href="https://ani.gamer.com.tw/animeVideo.php?sn=' + item.sn +
				'" target="_blank" rel="noopener" class="text-gray-500 hover:text-cyan-400 ml-1.5 transition-colors" title="前往動畫瘋">' +
				'<i class="fas fa-external-link-alt text-xs"></i></a>';

			var rowClass = item.in_sn_list ? 'subscribed-row' : '';
			var row = '<tr class="' + rowClass + ' hover:bg-gray-800/50">' +
				'<td class="px-3 py-2 text-gray-400">' + (item.time || '-') + '</td>' +
				'<td class="px-3 py-2">' + safeTitle + animeLink + '</td>' +
				'<td class="px-3 py-2 text-gray-400">' + item.sn + '</td>' +
				'<td class="px-3 py-2 ' + statusClass + '">' + statusText + '</td>' +
				'<td class="px-3 py-2 whitespace-nowrap">' + actions + '</td>' +
				'</tr>';
			tbody.append(row);
		}
	}

	// 自動捲動至今天的星期
	if (todayHeaderId) {
		setTimeout(function() {
			var header = document.getElementById(todayHeaderId);
			if (header) header.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}, 100);
	}
}

// --- 訂閱表單 ---
function showSubscribeForm(sn, title, btnEl) {
	var div = document.createElement('div');
	div.innerHTML = title;
	var cleanTitle = div.textContent || div.innerText || '';

	$('#sub_sn').val(sn);
	$('#sub_folder').val(cleanTitle);
	$('#sub_title').val('');
	$('#sub_season').val('1');
	$('#sub_ep_offset').val('0');
	$('#sub_comment').val('');
	$('#sub_sn_info').text('');
	$('#sub_mode').val('latest');
	updateSubscribePreview();

	// 移除先前插入的表單行
	$('.subscribe-form-row').remove();

	// 將表單插入到點擊行的下方
	var $form = $('#subscribe_form').removeClass('hidden');
	var $clickedRow = btnEl ? $(btnEl).closest('tr') : null;
	if ($clickedRow && $clickedRow.length) {
		var $formRow = $('<tr class="subscribe-form-row"><td colspan="5" class="p-0"></td></tr>');
		$formRow.find('td').append($form);
		$clickedRow.after($formRow);
		// 捲動至表單
		setTimeout(function() {
			$form[0].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
		}, 50);
	}

	fetchFirstSn();
}

function hideSubscribeForm() {
	var $form = $('#subscribe_form').addClass('hidden');
	// 將表單移回原位（排程表格外的隱藏容器）
	$('#subscribe_form_anchor').append($form);
	$('.subscribe-form-row').remove();
}

function fetchFirstSn() {
	var sn = $('#sub_sn').val();
	if (!sn) return;

	$('#sub_sn_info').text('正在查詢第一集...').removeClass('text-red-400').addClass('text-gray-500');
	$.ajax({
		type: 'get',
		url: 'data/anime_first_sn?sn=' + sn,
		dataType: 'json',
		success: function(data) {
			if (data.error) {
				$('#sub_sn_info').text('查詢失敗：' + data.error).removeClass('text-gray-500').addClass('text-red-400');
			} else {
				$('#sub_sn').val(data.first_sn);
				var info = '第一集 SN: ' + data.first_sn;
				if (data.title) info += ' — ' + data.title;
				$('#sub_sn_info').text(info).removeClass('text-red-400').addClass('text-gray-500');
				if (data.title && !$('#sub_folder').val().trim()) {
					$('#sub_folder').val(data.title);
				}
				updateSubscribePreview();
			}
		},
		error: function(xhr) {
			var msg = '查詢失敗';
			try { var r = JSON.parse(xhr.responseText); if (r.error) msg += '：' + r.error; } catch(e) {}
			$('#sub_sn_info').text(msg).removeClass('text-gray-500').addClass('text-red-400');
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
				showSnList(); // 同步刷新 sn_list textarea
				loadBahaSchedule(false);
				setTimeout(function() { loadTimetable(); }, 2000);
			} else {
				alert('訂閱失敗：' + (data.error || '未知錯誤'));
			}
		},
		error: function() { alert('訂閱失敗：網路錯誤'); }
	});
}

// --- 取消訂閱 ---
function unsubscribeAnime(title) {
	var div = document.createElement('div');
	div.innerHTML = title;
	var cleanTitle = div.textContent || div.innerText || '';

	if (!confirm('確定要取消訂閱「' + cleanTitle + '」嗎？')) return;

	$.ajax({
		type: 'post',
		url: 'schedule/unsubscribe',
		data: JSON.stringify({ title: cleanTitle }),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.removed) {
				alert('已取消訂閱 (SN=' + data.sn + ')');
				showSnList(); // 同步刷新 sn_list textarea
				loadBahaSchedule(false);
				setTimeout(function() { loadTimetable(); }, 2000);
			} else {
				alert('取消訂閱失敗：' + (data.error || '未找到對應條目'));
			}
		},
		error: function() { alert('取消訂閱失敗：網路錯誤'); }
	});
}

// --- 立即檢查 ---
function forceCheckAnime(title) {
	var div = document.createElement('div');
	div.innerHTML = title;
	var cleanTitle = div.textContent || div.innerText || '';

	$.ajax({
		type: 'post',
		url: 'schedule/force_check',
		data: JSON.stringify({ title: cleanTitle }),
		contentType: 'application/json',
		dataType: 'json',
		success: function(data) {
			if (data.status === 200) {
				alert('已排入立即檢查 (SN=' + data.sn + ')\n將在數秒內自動開始');
			} else {
				alert('操作失敗：' + (data.error || '未知錯誤'));
			}
		},
		error: function() { alert('操作失敗：網路錯誤'); }
	});
}

// === 任務監控底部抽屜 ===
var monitorInterval = null;
var logInterval = null;
var monitorKnownTasks = {};
var lastLogLine = '';
var drawerOpen = false;

function toggleDrawer() {
	if (drawerOpen) {
		closeDrawer();
	} else {
		openDrawer();
	}
}

function openDrawer() {
	drawerOpen = true;
	$('#monitorDrawer').addClass('expanded');
	$('#drawerContent').css('max-height', '50vh');
	fetchMonitorTasks();
	fetchMonitorLogs();
	monitorInterval = setInterval(fetchMonitorTasks, 1000);
	logInterval = setInterval(fetchMonitorLogs, 2000);
}

function closeDrawer() {
	drawerOpen = false;
	$('#monitorDrawer').removeClass('expanded');
	$('#drawerContent').css('max-height', '0');
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
		var taskCount = Object.keys(data).length;

		// 更新抽屜狀態列任務數
		var badge = $('#drawerTaskCount');
		if (taskCount > 0) {
			badge.text(taskCount).removeClass('hidden bg-gray-800 text-gray-400').addClass('bg-cyan-600 text-white');
		} else {
			badge.text('0').removeClass('bg-cyan-600 text-white').addClass('hidden');
		}

		for (var sn in data) {
			hasTask = true;
			var task = data[sn];
			var pct = Math.round(task.rate || 0);
			var existing = container.find('#mt_' + sn);

			if (existing.length > 0) {
				existing.find('.mt-name').text(task.filename || 'SN=' + sn);
				existing.find('.monitor-task-fill').css('width', pct + '%');
				existing.find('.mt-pct').text(pct + '%');
				existing.find('.mt-status').text(task.status || '');
			} else {
				var html = '<div class="bg-gray-800 rounded-md p-3 mb-2" id="mt_' + sn + '">'
					+ '<div class="mt-name text-sm text-gray-200 mb-1 truncate">' + escapeHtml(task.filename || 'SN=' + sn) + '</div>'
					+ '<div class="monitor-task-bar"><div class="monitor-task-fill" style="width:' + pct + '%"></div></div>'
					+ '<div class="flex justify-between text-xs text-gray-400 mt-1"><span class="mt-status">' + escapeHtml(task.status || '') + '</span><span class="mt-pct">' + pct + '%</span></div>'
					+ '</div>';
				container.append(html);
			}
			monitorKnownTasks[sn] = true;
		}

		for (var knownSn in monitorKnownTasks) {
			if (!(knownSn in data)) {
				container.find('#mt_' + knownSn).remove();
				delete monitorKnownTasks[knownSn];
			}
		}

		$('#monitorNoTask').toggle(!hasTask);
	});
}

function fetchMonitorLogs() {
	$.get('data/recent_logs?n=80', function(data) {
		if (typeof data === 'string') {
			try { data = JSON.parse(data); } catch(e) { return; }
		}
		var lines = data.lines || [];
		var currentLast = lines.length > 0 ? lines[lines.length - 1] : '';
		if (currentLast === lastLogLine && lines.length > 0) return;
		lastLogLine = currentLast;

		var container = $('#monitorLogs');
		var wasAtBottom = container[0].scrollHeight - container[0].scrollTop - container[0].clientHeight < 30;

		var html = '';
		for (var i = 0; i < lines.length; i++) {
			var line = lines[i];
			var cls = 'monitor-log-line';
			if (/失[敗败]|ERROR|錯誤|错误/.test(line)) {
				cls += ' log-error';
			} else if (/完成|成功|Refresh/.test(line)) {
				cls += ' log-success';
			}
			html += '<div class="' + cls + '">' + escapeHtml(line) + '</div>';
		}
		container.html(html);

		if (wasAtBottom) {
			container[0].scrollTop = container[0].scrollHeight;
		}
	});
}

// === 鍵盤快捷鍵 ===
$(document).on('keydown', function(e) {
	// ESC: 關閉最上層介面（modal > 訂閱表單 > 抽屜）
	if (e.key === 'Escape') {
		var modals = ['uploadStatusModal', 'scheduleModal', 'manualTaskModal', 'snListModal'];
		for (var i = 0; i < modals.length; i++) {
			var el = document.getElementById(modals[i]);
			if (el && !el.classList.contains('hidden')) {
				closeModal(modals[i]);
				return;
			}
		}
		var subForm = document.getElementById('subscribe_form');
		if (subForm && !subForm.classList.contains('hidden')) {
			hideSubscribeForm();
			return;
		}
		return;
	}

	// 排除表單元素（避免打字時誤觸）
	var tag = (e.target.tagName || '').toLowerCase();
	if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;

	// T: Toggle 任務監控抽屜
	if (e.key === 't' || e.key === 'T') {
		e.preventDefault();
		toggleDrawer();
	}
});
