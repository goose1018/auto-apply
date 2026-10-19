"""User-visible bilingual text (CODE_STANDARDS §3). Tool layer; pure data + one lookup function."""

from __future__ import annotations

from autoapply.errors import UsageError

# gate_type -> (zh, en) default "what you do" instructions for pending_actions.md
GATE_USER_INSTRUCTIONS: dict[str, tuple[str, str]] = {
    "password_or_signup": (
        "在页面上自己输入密码并让 Chrome 保存（不要把密码贴到会话），完成后说「继续」。",
        "Type the password on the page yourself and let Chrome save it (never paste it into the chat), then say \"continue\".",
    ),
    "captcha": ("在页面上自己完成人机验证，完成后说「继续」。", "Solve the CAPTCHA on the page yourself, then say \"continue\"."),
    "otp": (
        "把邮件/短信里的验证码贴到会话（不要贴密码），或自己在页面输入完成后说「继续」。",
        "Paste the one-time code into the chat (never a password), or enter it on the page yourself and say \"continue\".",
    ),
    "email_verification_link": ("到邮箱点击账号验证链接，完成后说「继续」。", "Open the verification link in your mailbox, then say \"continue\"."),
    "id_number": (
        "该表单要求证件号，工具不会填写。你可以自己完成该申请并说「我自己投了」，或说「跳过」。",
        "This form requires a government ID number, which the tool never fills. Complete it yourself and say \"done myself\", or say \"skip\".",
    ),
    "payment": ("该表单出现支付/银行字段，工具不会填写。请自行决定是否继续。", "This form asks for payment/bank details, which the tool never fills. Decide yourself whether to proceed."),
    "personal_declaration": ("这道声明题必须由你本人回答。请在会话里给出答案，或在页面自己作答后说「继续」。", "This declaration must be answered by you. Reply in the chat, or answer on the page and say \"continue\"."),
    "final_submit": ("复核清单已通过。请回复「提交」或「跳过」。", "Pre-submit checks passed. Reply \"submit\" or \"skip\"."),
    "content_approval": ("请审阅草稿：回复「批准」、给出修改意见，或「跳过」。", "Review the draft: reply \"approve\", give edits, or \"skip\"."),
    "resume_missing_language": ("岗位要求另一种语言的简历。请补一份简历到档案，或说「跳过」。", "This posting needs a resume in another language. Add one to your profile, or say \"skip\"."),
    "unknown_required_field": ("表单需要档案中没有的字段。请在会话里补充这些值（会写入档案），或说「跳过」。", "The form needs fields missing from your profile. Provide them in the chat (they will be saved to the profile), or say \"skip\"."),
    "file_upload_blocked": ("浏览器扩展无法上传文件。请在扩展设置开启文件访问，或自己在页面选择文件后说「继续」。", "The browser extension cannot upload files. Enable file access in the extension settings, or pick the file on the page yourself and say \"continue\"."),
    "session_expired": ("页面会话已失效。请重新登录后说「继续」。", "The page session expired. Log in again, then say \"continue\"."),
    "dedup_review": ("这条疑似与已投岗位重复。请确认「投」或「跳过」。", "This looks like a duplicate of an application already made. Confirm \"apply\" or \"skip\"."),
    "queue_approval": ("请审阅母清单：说「全部批准」或列出要排除的编号。", "Review the shortlist: say \"approve all\" or list the numbers to exclude."),
    "consistency_mismatch": ("简历与档案不一致。请选择：① 以档案为准 ② 换一份简历 ③ 改档案为简历上的值。", "Resume and profile disagree. Choose: (1) keep the profile, (2) use a different resume, (3) update the profile to match the resume."),
    "browser_disconnected": ("浏览器扩展已断开。请确认扩展已连接、Chrome 已登录，然后说「继续」。", "The browser extension is disconnected. Check the extension and Chrome login, then say \"continue\"."),
    "quota_exhausted": ("今日投递配额已用完。可以说「提高今日上限到 N」或等待明天。", "Today's application quota is used up. Say \"raise today's limit to N\" or wait until tomorrow."),
}

PRIORITY_LABEL: dict[str, tuple[str, str]] = {"high": ("高", "high"), "normal": ("中", "normal"), "low": ("低", "low")}


def gate_instructions(gate_type: str) -> tuple[str, str]:
    try:
        return GATE_USER_INSTRUCTIONS[gate_type]
    except KeyError as e:
        raise UsageError("未知 gate_type / unknown gate_type", {"gate_type": gate_type}) from e
