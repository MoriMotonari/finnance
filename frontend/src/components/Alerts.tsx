import { Alert, Code, createStyles } from "@mantine/core";
import { TbAlertCircle } from "react-icons/tb";
import { RiZzzFill } from "react-icons/ri";

interface AlertProps {
    msg?: string,
}

export function FrontendErrorAlert({ msg }: AlertProps) {
    return <Alert
        icon={<TbAlertCircle />}
        title="Oops!" color="red"
        variant="filled"
        >
        Something terrible happened!
        <br/>
        The Frontend didn't render due to
        <br/>
        <Code>{msg}</Code>
        <br/>
        Please contact the developer or try again later!
    </Alert>
}