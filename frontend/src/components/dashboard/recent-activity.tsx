import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { CardBase as Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function RecentActivity() {
  return (
    <Card className="col-span-3 border-gray-800 bg-gray-900/50 text-white">
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-8">
          <div className="flex items-center">
            <Avatar className="h-9 w-9">
              <AvatarImage src="/avatars/01.png" alt="Avatar" />
              <AvatarFallback>OM</AvatarFallback>
            </Avatar>
            <div className="ml-4 space-y-1">
              <p className="text-sm font-medium leading-none">Cost Anomaly Detected</p>
              <p className="text-sm text-gray-400">
                EC2 usage spiked by 45% in us-east-1
              </p>
            </div>
            <div className="ml-auto font-medium text-red-500">+$249.00</div>
          </div>
          <div className="flex items-center">
            <Avatar className="flex h-9 w-9 items-center justify-center space-y-0 border">
              <AvatarImage src="/avatars/02.png" alt="Avatar" />
              <AvatarFallback>JL</AvatarFallback>
            </Avatar>
            <div className="ml-4 space-y-1">
              <p className="text-sm font-medium leading-none">Budget Alert</p>
              <p className="text-sm text-gray-400">
                Monthly budget forecast exceeded 80%
              </p>
            </div>
            <div className="ml-auto font-medium text-yellow-500">Warning</div>
          </div>
          <div className="flex items-center">
            <Avatar className="h-9 w-9">
              <AvatarImage src="/avatars/03.png" alt="Avatar" />
              <AvatarFallback>IN</AvatarFallback>
            </Avatar>
            <div className="ml-4 space-y-1">
              <p className="text-sm font-medium leading-none">New Account Linked</p>
              <p className="text-sm text-gray-400">
                AWS Production Account connected
              </p>
            </div>
            <div className="ml-auto font-medium text-green-500">Success</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
