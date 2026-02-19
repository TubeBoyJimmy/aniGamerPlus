layui.use('element', function(){
	let element = layui.element;
	let knownTasks = {};  // 追蹤已顯示的任務卡片

	function fetchProgress() {
		$.get('data/tasks_progress', function(data){
			if (typeof data === 'string') {
				try { data = JSON.parse(data); } catch(e) { return; }
			}

			if (Object.keys(data).length == 0){
				$('#no_task').show();
			} else {
				$('#no_task').hide();
				for (let sn in data){
					if ($('#'+sn).length > 0) {
						// 如果该任务卡片已存在
						$("#status"+sn).html(data[sn]["status"]);
						$("#header"+sn).html(data[sn]["filename"]);
						element.progress(sn, Math.round(data[sn]["rate"])+'%');
					} else {
						// 如果该任务卡片不存在
						let task_item_templates = `
							<div class="layui-col-xs12 layui-card" id=${sn}>
								<div class="layui-card-header" style="height:auto !important;" id=${"header"+sn}>${data[sn]["filename"]}</div>
								<div class="layui-card-body layui-row">
									<div class="layui-col-xs3" style="text-align: center;" id=${"status"+sn}>${data[sn]["status"]}</div>
									<div class="layui-col-xs9" style="padding: 3px;">
										<div class="layui-progress layui-progress-big" lay-showpercent="true" lay-filter=${sn}>
											<div class="layui-progress-bar" lay-percent="0%">
												<span class="layui-progress-text">0%</span>
											</div>
										</div>
									</div>
								</div>
							</div>
						`;
						$("#task_info_panel").prepend(task_item_templates);
						element.progress();
					}
					knownTasks[sn] = true;
				}
			}

			// 移除已完成的任務卡片 (不在回傳資料中的)
			for (let sn in knownTasks) {
				if (!(sn in data)) {
					$('#'+sn).remove();
					delete knownTasks[sn];
				}
			}
		}).fail(function(){
			// 請求失敗時不做處理, 等下次輪詢
		});
	}

	// 立即執行一次, 然後每秒輪詢
	fetchProgress();
	setInterval(fetchProgress, 1000);
});
