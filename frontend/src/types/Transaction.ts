import { UseFormReturnType, useForm } from "@mantine/form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import axios, { AxiosError } from "axios"
import { DateTime, Duration } from "luxon"
import { useEffect, useState } from "react"
import { AccountQueryResult } from "./Account"
import { AgentQueryResult } from "./Agent"
import { CurrencyQueryResult } from "./Currency"
import { FlowFormValues, FlowQueryResult, FlowRequest, flowsFormValues, isFlow } from "./Flow"
import { RecordFormValues, RecordQueryResult, RecordRequest, isRecord, recordsFormValues } from "./Record"

export interface TransactionQueryResult {
    id: number,
    currency_id: number,
    agent_id: number,
    comment: string,
    amount: number,
    is_expense: boolean,
    account_id: number | null,
    date_issued: string,
    user_id: number,
    type: 'transaction',
}

export interface TransactionDeepQueryResult extends TransactionQueryResult {
    agent: AgentQueryResult,
    account: AccountQueryResult,
    currency: CurrencyQueryResult,
    records: RecordQueryResult[]
    flows: FlowQueryResult[]
}

export interface TransactionFormValues {
    account_id: string | null
    currency_id: string | null
    date: Date
    time: string
    amount: number | ''
    is_expense: boolean
    agent: string
    comment: string

    direct: boolean
    remote_agent: string | undefined
    n_flows: number
    n_records: number
    last_update: number
    items: (FlowFormValues | RecordFormValues)[]
}

export interface TransactionRequest {
    account_id: number | undefined
    currency_id: number | undefined
    date_issued: string
    amount: number
    agent: string
    is_expense: boolean
    flows: FlowRequest[]
    records: RecordRequest[]
    comment: string
    remote_agent: string | undefined
}

export type TransactionTransform = (v: TransactionFormValues) => TransactionRequest
export type TransactionFormType = UseFormReturnType<TransactionFormValues, TransactionTransform>

export const datetimeString = (date: Date, timeS: string): string => {
    const time = DateTime.fromFormat(timeS, "HH:mm")
    return DateTime.fromJSDate(date).startOf('day').plus(Duration.fromObject({
        hour: time.hour,
        minute: time.minute
    })).toISO({ includeOffset: false })
}

export const useTransactionForm = (initial: TransactionFormValues) => {
    const form = useForm<TransactionFormValues, TransactionTransform>({
        initialValues: initial,
        validate: {
            currency_id: (val, fv) => val === null ? 'choose currency' : null,
            time: val => val === '' ? 'enter time' : null,
            amount: val => val === '' ? 'enter amount' : null,
            agent: desc => desc.length === 0 ? "at least one character" : null,
            direct: (val, fv) => !val && fv.items.length === 0 ? 'at least one record or flow' : null,
            items: {
                agent: (desc, fv, path) => {
                    const i = parseInt(path.replace(/^\D+/g, ''));
                    if (fv.direct || isRecord(fv.items[i]))
                        return null;
                    if (desc.length === 0)
                        return 'at least one character';
                    for (let j = 0; j < i; j++) {
                        const item = fv.items[j];
                        if (isFlow(item) && item.agent === desc)
                            return 'duplicate agent';
                    }
                    return null;
                },
                category_id: (id, fv, path) => {
                    const i = parseInt(path.replace(/^\D+/g, ''));
                    if (fv.direct || isFlow(fv.items[i]))
                        return null;
                    if (id === null)
                        return 'select category';
                    for (let j = 0; j < i; j++) {
                        const item = fv.items[j];
                        if (isRecord(item) && item.category_id === id)
                            return 'duplicate category';
                    }
                    return null;
                },
                amount: (value, fv, path) => {
                    if (fv.direct)
                        return null;
                    if (value === '')
                        return 'enter amount';
                    if (value === 0)
                        return 'non-zero amount';
                    const i = parseInt(path.replace(/^\D+/g, ''));
                    const sum = fv.items.slice(0, i + 1).reduce(
                        (sum, item) => sum + (item.amount === '' ? 0 : item.amount), 0
                    );
                    if (fv.amount !== '' && sum > fv.amount)
                        return 'exceeds total';
                    if (i === fv.items.length - 1 && fv.amount !== '' && sum < fv.amount)
                        return 'less than total';
                    return null;
                }
            }
        },
        transformValues: (fv: TransactionFormValues) => ({
            account_id: fv.account_id === null ? undefined : parseInt(fv.account_id),
            currency_id: fv.currency_id === null ? undefined : parseInt(fv.currency_id),
            is_expense: fv.is_expense,
            agent: fv.agent,
            amount: fv.amount ? fv.amount : 0,
            comment: fv.comment,
            date_issued: datetimeString(fv.date, fv.time),
            flows: fv.direct ?
                [{ amount: fv.amount ? fv.amount : 0, agent: fv.agent }]
                :
                fv.items.filter(isFlow).map(item => ({
                    amount: item.amount ? item.amount : 0,
                    agent: item.agent
                })),
            records: fv.direct ?
                [] : fv.items.filter(isRecord)
                    .map(item => ({
                        amount: item.amount ? item.amount : 0,
                        category_id:
                            item.category_id === null ? -1 : parseInt(item.category_id)
                    })),
            remote_agent: fv.remote_agent
        })
    });

    // auto-adjust item amounts
    // lil bit sketchy tbh
    useEffect(() => form.setFieldValue('last_update', -1),
        // eslint-disable-next-line
        [form.values.amount, form.values.n_flows, form.values.n_records])

    const sum = form.values.items.reduce(
        (sum, item) => sum + (item.amount === '' ? 0 : item.amount), 0
    );
    useEffect(() => {
        // without the 20ms the form's not ready
        new Promise(r => setTimeout(r, 20)).then(() => {
            const total = form.values.amount;
            if (total === '' || form.values.items.length === 0) {
                form.setFieldValue('last_update', -1);
                return;
            }
            let toCorrect = (total - sum);
            form.values.items.forEach((item, i) => {
                if (toCorrect === 0 || i === form.values.last_update)
                    return;
                const correct = Math.max(-item.amount, toCorrect);
                form.setFieldValue(`items.${i}.amount`, (item.amount === '' ? 0 : item.amount) + correct);
                toCorrect -= correct;
            })
            form.setFieldValue('last_update', -1);
        })
        // eslint-disable-next-line
    }, [form.values.amount, sum, form.values.n_flows, form.values.n_records])

    return form;
}

export const useTransactionFormValues:
    (t?: TransactionDeepQueryResult, a?: AccountQueryResult)
        => TransactionFormValues
    = (trans, acc) => {
        const build: () => TransactionFormValues = () => trans ? {
            account_id: trans.account_id === null ?
                null : trans.account_id.toString(),
            currency_id: trans.currency_id.toString(),
            date: DateTime.fromISO(trans.date_issued).startOf('day').toJSDate(),
            time: DateTime.fromISO(trans.date_issued).toFormat('HH:mm'),
            amount: trans.amount,
            is_expense: trans.is_expense,
            agent: trans.agent.desc,
            direct: trans.flows.length === 1 && trans.flows[0].agent_id === trans.agent_id,
            n_flows: trans.flows.length,
            n_records: trans.records.length,
            items: recordsFormValues(trans.records, 0)
                .concat(
                    trans.account_id === null ?
                        [] : flowsFormValues(trans.flows, trans.records.length)
                ),
            comment: trans.comment,
            last_update: -1,
            remote_agent: trans.account_id === null ?
                trans.flows[0].agent_desc : undefined,
        } : {
            account_id: acc ? acc.id.toString() : null,
            currency_id: acc ? acc.currency_id.toString() : null,
            date: new Date(),
            time: DateTime.now().toFormat('HH:mm'),
            amount: '',
            is_expense: true,
            agent: '',
            direct: false,
            n_flows: 0,
            n_records: 0,
            items: [],
            comment: '',
            last_update: -1,
            remote_agent: acc ? undefined : ''
        }
        const [fv, setFV] = useState(build());
        // eslint-disable-next-line
        useEffect(() => setFV(build()), [trans, acc]);
        return fv;
    }

export const useTransaction = (trans_id: number) =>
    useQuery<TransactionDeepQueryResult, AxiosError>({ queryKey: ['transactions', trans_id] });

export const useAddTransaction = () => {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (values: TransactionRequest) =>
            axios.post('/api/transactions/add', values),
        onSuccess: () => {
            queryClient.invalidateQueries(['changes']);
            queryClient.invalidateQueries(['transactions']);
            queryClient.invalidateQueries(['accounts']);
        }
    });
}

export const useEditTransaction = () => {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, values }: { id: number, values: TransactionRequest }) =>
            axios.put(`/api/transactions/${id}/edit`, values),
        onSuccess: () => {
            queryClient.invalidateQueries(['changes']);
            queryClient.invalidateQueries(['transactions']);
            queryClient.invalidateQueries(['accounts']);
        }
    });
}