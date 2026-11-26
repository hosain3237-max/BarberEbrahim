package ir.ebrahim.salon;
import android.app.*;
import android.os.Build;
import android.content.*;
import com.google.firebase.messaging.*;

public class ReminderService extends FirebaseMessagingService {
    private static final String CHANNEL="salon_reminders";
    static void channel(Context c){if(Build.VERSION.SDK_INT>=26)c.getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel(CHANNEL,"یادآوری نوبت",NotificationManager.IMPORTANCE_DEFAULT));}
    @Override public void onMessageReceived(RemoteMessage msg){
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=0)return;
        RemoteMessage.Notification n=msg.getNotification(); if(n==null)return;
        channel(this);
        Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(this,CHANNEL):new Notification.Builder(this);
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        getSystemService(NotificationManager.class).notify((int)System.currentTimeMillis(),b.setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(n.getTitle()).setContentText(n.getBody()).setContentIntent(open).setAutoCancel(true).build());
    }
}
