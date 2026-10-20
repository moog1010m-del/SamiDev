package com.samidev.platform

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "plazr/notifications").setMethodCallHandler { call, result ->
            if (call.method == "createChannel") {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    val channel = NotificationChannel("plazr_friends", "رسائل الأصدقاء", NotificationManager.IMPORTANCE_HIGH)
                    channel.description = "إشعارات الرسائل الخاصة في Plazr"
                    getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
                    val games = NotificationChannel("plazr_games", "المباريات والأدوار", NotificationManager.IMPORTANCE_HIGH)
                    games.description = "بدء المباراة ووصول دورك في الطاولة"
                    getSystemService(NotificationManager::class.java).createNotificationChannel(games)
                }
                result.success(null)
            } else if (call.method == "configuration") {
                fun value(name: String): String {
                    val id = resources.getIdentifier(name, "string", packageName)
                    return if (id == 0) "" else resources.getString(id)
                }
                result.success(mapOf("projectId" to value("project_id"), "appId" to value("google_app_id")))
            } else result.notImplemented()
        }
    }
}
